"""
Refresh manager for Celery tasks and data synchronization
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
from typing import Dict, Any, List, Optional
from analytics.constants import (
    CELERY_TASK_RETRY_DELAY,
    CELERY_MAX_RETRIES,
    METRICS_REFRESH_THRESHOLD_HOURS
)
from analytics.github.enhanced_github_client import EnhancedGitHubClient
from analytics.metrics.metrics_service import MetricsService
from core.models import User, Repository, UserMetrics

logger = logging.getLogger(__name__)


class RefreshManager:
    """Manages data refresh operations and Celery tasks"""
    
    def __init__(self):
        self.metrics_service = MetricsService()
        
    def refresh_user_metrics_sync(self, user_id: int, force_refresh: bool = False):
        """Celery task to refresh metrics for a specific user"""
        try:
            user = User.objects.get(id=user_id)
            
            if not user.github_token:
                logger.warning(f"No GitHub token for user {user_id}")
                return {'error': 'No GitHub token available'}
            
            # Check if refresh is needed
            if not force_refresh and not self._should_refresh_user(user):
                logger.info(f"Skipping refresh for user {user_id} - not needed")
                return {'status': 'skipped', 'reason': 'refresh not needed'}
            
            github_client = EnhancedGitHubClient(user.github_token)
            
            # Get user repositories
            repositories = Repository.objects.filter(
                userrepository__user=user,
                userrepository__is_active=True
            )
            
            total_metrics = []
            
            for repo in repositories:
                try:
                    # Fetch GitHub data
                    commits = github_client.fetch_commits(repo.owner, repo.name)
                    pull_requests = github_client.fetch_pull_requests(repo.owner, repo.name)
                    issues = []  # TODO: Add fetch_issues method to GitHubClient
                    
                    # Calculate metrics
                    repo_metrics = self.metrics_service.calculate_all_metrics(
                        commits, pull_requests, 'repository'
                    )
                    
                    if repo_metrics:
                        repo_metrics['repository_id'] = repo.id
                        repo_metrics['repository_name'] = f"{repo.owner}/{repo.name}"
                        total_metrics.append(repo_metrics)
                        
                except Exception as e:
                    logger.error(f"Error processing repo {repo.owner}/{repo.name}: {str(e)}")
                    continue
            
            if total_metrics:
                # Store aggregated metrics
                aggregated_metrics = self._aggregate_metrics(total_metrics)
                
                UserMetrics.objects.create(
                    user=user,
                    metrics_data=aggregated_metrics,
                    calculated_at=timezone.now()
                )
                
                logger.info(f"Successfully refreshed metrics for user {user_id}")
                return {
                    'status': 'success',
                    'user_id': user_id,
                    'repositories_processed': len(total_metrics),
                    'metrics': aggregated_metrics
                }
            else:
                logger.warning(f"No metrics calculated for user {user_id}")
                return {'status': 'no_data', 'user_id': user_id}
                
        except User.DoesNotExist:
            logger.error(f"User {user_id} not found")
            return {'error': 'User not found'}
            
        except Exception as e:
            logger.error(f"Error refreshing metrics for user {user_id}: {str(e)}")
            raise e
    
    def refresh_all_active_users(self):
        """Celery task to refresh metrics for all active users"""
        try:
            active_users = User.objects.filter(
                github_token__isnull=False,
                is_active=True
            )
            
            results = []
            
            for user in active_users:
                try:
                    # For now, call sync method directly (async task will be called externally)
                    result = self.refresh_user_metrics_sync(user.id)
                    results.append({
                        'user_id': user.id,
                        'status': 'completed',
                        'result': result
                    })
                except Exception as e:
                    logger.error(f"Error queuing refresh for user {user.id}: {str(e)}")
                    results.append({
                        'user_id': user.id,
                        'status': 'error',
                        'error': str(e)
                    })
            
            logger.info(f"Queued refresh tasks for {len(results)} users")
            return {
                'status': 'success',
                'users_queued': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error in refresh_all_active_users: {str(e)}")
            raise e
    
    def _should_refresh_user(self, user: User) -> bool:
        """Check if user metrics should be refreshed"""
        try:
            latest_metrics = UserMetrics.objects.filter(user=user).order_by('-calculated_at').first()
            
            if not latest_metrics:
                return True
            
            # Check if last refresh was more than REFRESH_INTERVAL_MINUTES ago
            cutoff_time = timezone.now() - timedelta(hours=METRICS_REFRESH_THRESHOLD_HOURS)
            return latest_metrics.metric_timestamp < cutoff_time
            
        except Exception as e:
            logger.error(f"Error checking refresh status for user {user.id}: {str(e)}")
            return True  # Err on side of refreshing
    
    def _aggregate_metrics(self, repo_metrics_list: List[Dict]) -> Dict[str, Any]:
        """Aggregate repository metrics into user-level metrics"""
        if not repo_metrics_list:
            return {}
        
        try:
            # Sum up totals
            total_commits = sum(m.get('total_commits', 0) for m in repo_metrics_list)
            total_prs = sum(m.get('total_prs', 0) for m in repo_metrics_list)
            
            # Calculate averages for rate metrics
            deployment_frequencies = [m.get('deployment_frequency', 0) for m in repo_metrics_list if m.get('deployment_frequency', 0) > 0]
            lead_times = [m.get('lead_time_for_changes', 0) for m in repo_metrics_list if m.get('lead_time_for_changes', 0) > 0]
            mttrs = [m.get('mean_time_to_recovery', 0) for m in repo_metrics_list if m.get('mean_time_to_recovery', 0) > 0]
            change_failure_rates = [m.get('change_failure_rate', 0) for m in repo_metrics_list if m.get('change_failure_rate', 0) > 0]
            
            aggregated = {
                'total_commits': total_commits,
                'total_prs': total_prs,
                'repositories_count': len(repo_metrics_list),
                'deployment_frequency': sum(deployment_frequencies) / len(deployment_frequencies) if deployment_frequencies else 0,
                'lead_time_for_changes': sum(lead_times) / len(lead_times) if lead_times else 0,
                'mean_time_to_recovery': sum(mttrs) / len(mttrs) if mttrs else 0,
                'change_failure_rate': sum(change_failure_rates) / len(change_failure_rates) if change_failure_rates else 0,
                'calculated_at': timezone.now().isoformat()
            }
            
            # Calculate overall performance grade
            aggregated['performance_grade'] = self.metrics_service.get_performance_grade(aggregated)
            
            return aggregated
            
        except Exception as e:
            logger.error(f"Error aggregating metrics: {str(e)}")
            return {}


# Utility functions for manual refresh operations
def refresh_user_now(user_id: int) -> Dict[str, Any]:
    """Manually trigger user metrics refresh"""
    manager = RefreshManager()
    return manager.refresh_user_metrics_sync(user_id, force_refresh=True)


def refresh_all_users_now() -> Dict[str, Any]:
    """Manually trigger refresh for all users"""
    manager = RefreshManager()
    return manager.refresh_all_active_users()


# Celery Tasks (standalone functions)
@shared_task(bind=True, max_retries=CELERY_MAX_RETRIES)
def refresh_user_metrics_task(self, user_id: int, force_refresh: bool = False):
    """Celery task to refresh metrics for a specific user"""
    try:
        manager = RefreshManager()
        return manager.refresh_user_metrics_sync(user_id, force_refresh)
    except Exception as e:
        logger.error(f"Error in refresh_user_metrics_task for user {user_id}: {str(e)}")
        if self.request.retries < CELERY_MAX_RETRIES:
            raise self.retry(countdown=CELERY_TASK_RETRY_DELAY)
        return {'error': str(e)}


@shared_task(bind=True, max_retries=CELERY_MAX_RETRIES)  
def refresh_all_users_task(self):
    """Celery task to refresh metrics for all active users"""
    try:
        manager = RefreshManager()
        return manager.refresh_all_active_users()
    except Exception as e:
        logger.error(f"Error in refresh_all_users_task: {str(e)}")
        if self.request.retries < CELERY_MAX_RETRIES:
            raise self.retry(countdown=CELERY_TASK_RETRY_DELAY)
        return {'error': str(e)}