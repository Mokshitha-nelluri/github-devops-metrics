"""
Metrics Refresh Orchestrator
Migrated from backend/refresh_manager.py for Django
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.core.cache import cache
from django.conf import settings
import asyncio
import threading
from queue import Queue, Empty
import time

from core.services import DataService, GitHubService, MetricsService
from core.models import User, UserMetrics
from analytics.ml import MLService
from analytics.ai_summary import SummaryService

logger = logging.getLogger(__name__)


class MetricsRefreshOrchestrator:
    """
    Django-based metrics refresh orchestrator
    Manages intelligent caching, rate limiting, and background processing
    """
    
    # Configuration constants
    RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
    MAX_REQUESTS_PER_HOUR = 4000  # GitHub API limit buffer
    CACHE_MAX_AGE_MINUTES = 15
    BACKGROUND_WORKER_SLEEP = 5
    PRIORITY_QUEUE_TIMEOUT = 30
    
    def __init__(self):
        self.data_service = DataService()
        self.metrics_service = MetricsService()
        
        # Rate limiting
        self.request_timestamps = []
        
        # Background processing
        self.background_worker_running = False
        self.priority_queue = Queue()
        self.worker_thread = None
        
    def should_refresh(self, cache_key: str, max_age_minutes: int = None) -> bool:
        """Check if data should be refreshed based on age and cache policy"""
        if max_age_minutes is None:
            max_age_minutes = self.CACHE_MAX_AGE_MINUTES
            
        cached_data = cache.get(f"timestamp_{cache_key}")
        if not cached_data:
            return True
            
        age = datetime.now() - cached_data
        return age > timedelta(minutes=max_age_minutes)
        
    def get_cached_metrics(self, cache_key: str) -> Optional[Dict]:
        """Get cached metrics if available and valid"""
        if not self.should_refresh(cache_key):
            return cache.get(cache_key)
        return None
        
    def cache_metrics(self, cache_key: str, metrics_data: Dict) -> None:
        """Cache metrics data with timestamp"""
        cache.set(cache_key, metrics_data, timeout=self.CACHE_MAX_AGE_MINUTES * 60)
        cache.set(f"timestamp_{cache_key}", datetime.now(), timeout=self.CACHE_MAX_AGE_MINUTES * 60)
        
    def is_rate_limited(self) -> bool:
        """Check if we're hitting GitHub API rate limits"""
        now = datetime.now()
        
        # Clean old timestamps
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if (now - ts).total_seconds() < self.RATE_LIMIT_WINDOW
        ]
        
        return len(self.request_timestamps) >= self.MAX_REQUESTS_PER_HOUR
        
    def add_request_timestamp(self) -> None:
        """Record a new API request timestamp"""
        self.request_timestamps.append(datetime.now())
        
    async def refresh_user_metrics(self, user_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Refresh metrics for a specific user
        """
        try:
            cache_key = f"metrics_{user_id}"
            
            # Check cache first
            if not force_refresh:
                cached = self.get_cached_metrics(cache_key)
                if cached:
                    return cached
                    
            # Check rate limiting
            if self.is_rate_limited():
                logger.warning(f"Rate limited - using cached data for user {user_id}")
                cached = cache.get(cache_key)
                if cached:
                    return cached
                return {'error': 'Rate limited and no cached data available'}
                
            # Get user
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return {'error': 'User not found'}
                
            if not user.github_token:
                return {'error': 'GitHub token not available'}
                
            # Record API usage
            self.add_request_timestamp()
            
            # Initialize services
            github_service = GitHubService(user.github_token)
            
            # Get user repositories
            repositories = self.data_service.get_user_repositories(user_id)
            
            all_metrics = []
            
            for repo in repositories:
                try:
                    # Fetch GitHub data
                    commits = github_service.fetch_commits(repo.owner, repo.name, days_back=30)
                    pull_requests = github_service.fetch_pull_requests(repo.owner, repo.name, days_back=30)
                    
                    # Calculate metrics
                    repo_metrics = self.metrics_service.calculate_all_metrics(
                        commits, pull_requests, 'repository'
                    )
                    
                    repo_metrics['repository'] = f"{repo.owner}/{repo.name}"
                    all_metrics.append(repo_metrics)
                    
                except Exception as e:
                    logger.error(f"Error processing repository {repo.owner}/{repo.name}: {e}")
                    continue
                    
            # Aggregate user metrics
            if all_metrics:
                user_metrics = self._aggregate_user_metrics(all_metrics)
                
                # Store in database
                self.data_service.store_user_metrics(user_id, user_metrics)
                
                # Cache results
                result = {
                    'user_id': user_id,
                    'metrics': user_metrics,
                    'repositories_processed': len(all_metrics),
                    'last_updated': datetime.now().isoformat()
                }
                
                self.cache_metrics(cache_key, result)
                return result
            else:
                return {
                    'user_id': user_id,
                    'error': 'No repository data available',
                    'repositories_processed': 0
                }
                
        except Exception as e:
            logger.error(f"Error refreshing metrics for user {user_id}: {e}")
            return {'error': f'Metrics refresh failed: {str(e)}'}
            
    def _aggregate_user_metrics(self, repo_metrics_list: List[Dict]) -> Dict[str, Any]:
        """Aggregate repository metrics into user-level metrics"""
        if not repo_metrics_list:
            return {}
            
        aggregated = {
            'total_commits': sum(m.get('total_commits', 0) for m in repo_metrics_list),
            'total_prs': sum(m.get('total_prs', 0) for m in repo_metrics_list),
            'repositories_count': len(repo_metrics_list),
        }
        
        # Calculate averages for timing metrics
        lead_times = [m.get('lead_time_hours', 0) for m in repo_metrics_list if m.get('lead_time_hours', 0) > 0]
        if lead_times:
            aggregated['avg_lead_time_hours'] = sum(lead_times) / len(lead_times)
            
        # Get performance grades
        grades = [m.get('performance_grade', {}) for m in repo_metrics_list if m.get('performance_grade')]
        if grades:
            # Use the best grade as overall grade
            grade_values = {'A+': 100, 'A': 95, 'A-': 90, 'B+': 85, 'B': 80, 'C': 70}
            best_grade = max(grades, key=lambda g: grade_values.get(g.get('overall_grade', 'C'), 0))
            aggregated['performance_grade'] = best_grade
            
        aggregated['date'] = datetime.now().isoformat()
        return aggregated
        
    def start_background_worker(self) -> None:
        """Start background worker for processing metrics"""
        if self.background_worker_running:
            return
            
        self.background_worker_running = True
        self.worker_thread = threading.Thread(target=self._background_worker, daemon=True)
        self.worker_thread.start()
        logger.info("Background metrics worker started")
        
    def stop_background_worker(self) -> None:
        """Stop background worker"""
        self.background_worker_running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)
        logger.info("Background metrics worker stopped")
        
    def _background_worker(self) -> None:
        """Background worker for processing priority refresh requests"""
        while self.background_worker_running:
            try:
                # Check for priority refresh requests
                try:
                    user_id = self.priority_queue.get(timeout=self.PRIORITY_QUEUE_TIMEOUT)
                    logger.info(f"Processing priority refresh for user {user_id}")
                    
                    # Run async refresh in sync context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(self.refresh_user_metrics(user_id, force_refresh=True))
                    loop.close()
                    
                    logger.info(f"Completed priority refresh for user {user_id}")
                    self.priority_queue.task_done()
                    
                except Empty:
                    # No priority requests, continue
                    pass
                    
                time.sleep(self.BACKGROUND_WORKER_SLEEP)
                
            except Exception as e:
                logger.error(f"Background worker error: {e}")
                time.sleep(self.BACKGROUND_WORKER_SLEEP)
                
    def queue_priority_refresh(self, user_id: str) -> None:
        """Queue a priority refresh for a user"""
        try:
            self.priority_queue.put_nowait(user_id)
            logger.info(f"Queued priority refresh for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to queue priority refresh for user {user_id}: {e}")
            
    def get_refresh_status(self) -> Dict[str, Any]:
        """Get current refresh system status"""
        return {
            'background_worker_running': self.background_worker_running,
            'priority_queue_size': self.priority_queue.qsize(),
            'recent_requests': len(self.request_timestamps),
            'rate_limited': self.is_rate_limited(),
            'cache_timeout_minutes': self.CACHE_MAX_AGE_MINUTES
        }


# Global orchestrator instance
_orchestrator = None

def get_orchestrator() -> MetricsRefreshOrchestrator:
    """Get global orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MetricsRefreshOrchestrator()
    return _orchestrator