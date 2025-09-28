"""
Django service layer for data operations
Replaces the original data_store.py functionality with Django ORM
"""
import logging
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.utils import timezone
from datetime import datetime
import json

from core.models import User, Repository, UserRepository, UserMetrics, RepositoryMetrics

logger = logging.getLogger(__name__)


class DataService:
    """
    Django service for data operations using Django ORM
    Replaces the original DataStore classes
    """
    
    def __init__(self):
        """Initialize Django-based data service"""
        logger.info("Django DataService initialized")
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None
    
    def ensure_user_exists_and_get_id(self, email: str, github_token: str = None, github_username: str = None) -> Optional[str]:
        """Ensure user exists in database and return user ID"""
        try:
            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'github_token': github_token,
                        'github_username': github_username
                    }
                )
                
                # Update GitHub token if provided and user already existed
                if not created and github_token:
                    user.github_token = github_token
                    user.github_username = github_username
                    user.save(update_fields=['github_token', 'github_username', 'updated_at'])
                
                logger.info(f"{'Created' if created else 'Updated'} user {email}")
                return str(user.id)
        except Exception as e:
            logger.error(f"Error ensuring user exists: {e}")
            return None
    
    def update_user_github_token(self, email: str, github_token: str, github_username: str = None) -> bool:
        """Update user's GitHub token"""
        try:
            user = self.get_user_by_email(email)
            if not user:
                return False
            
            user.github_token = github_token
            if github_username:
                user.github_username = github_username
            user.save(update_fields=['github_token', 'github_username', 'updated_at'])
            
            logger.info(f"GitHub token updated for {email}")
            return True
        except Exception as e:
            logger.error(f"Error updating GitHub token: {e}")
            return False
    
    def get_user_github_token(self, email: str) -> Optional[str]:
        """Get user's GitHub token"""
        try:
            user = self.get_user_by_email(email)
            return user.github_token if user else None
        except Exception as e:
            logger.error(f"Error getting GitHub token: {e}")
            return None
    
    def save_user_repo(self, user_email: str, repo_full_name: str) -> bool:
        """Save user repository association"""
        try:
            if '/' not in repo_full_name:
                logger.error(f"Invalid repo format: {repo_full_name}")
                return False
            
            owner, name = repo_full_name.split('/', 1)
            
            with transaction.atomic():
                # Get or create user
                user = self.get_user_by_email(user_email)
                if not user:
                    logger.error(f"User not found: {user_email}")
                    return False
                
                # Get or create repository
                repo, created = Repository.objects.get_or_create(
                    full_name=repo_full_name,
                    defaults={
                        'owner': owner,
                        'name': name
                    }
                )
                
                # Create user-repository association
                user_repo, created = UserRepository.objects.get_or_create(
                    user=user,
                    repository=repo
                )
                
                logger.info(f"{'Created' if created else 'Already exists'} association {user_email} -> {repo_full_name}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving user repo: {e}")
            return False
    
    def get_user_repos(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all repositories for a user"""
        try:
            user = User.objects.get(id=user_id)
            user_repos = UserRepository.objects.filter(user=user).select_related('repository')
            
            repos = []
            for user_repo in user_repos:
                repos.append({
                    'id': user_repo.id,  # UserRepository ID for deletion
                    'created_at': user_repo.created_at.isoformat(),
                    'repos': {
                        'id': user_repo.repository.id,
                        'owner': user_repo.repository.owner,
                        'name': user_repo.repository.name,
                        'full_name': user_repo.repository.full_name,
                        'description': user_repo.repository.description,
                        'language': user_repo.repository.language,
                        'stargazers_count': user_repo.repository.stargazers_count,
                        'forks_count': user_repo.repository.forks_count,
                    }
                })
            
            logger.info(f"Retrieved {len(repos)} repos for user {user.email}")
            return repos
            
        except User.DoesNotExist:
            logger.error(f"User not found: {user_id}")
            return []
        except Exception as e:
            logger.error(f"Error getting user repos: {e}")
            return []
    
    def delete_user_repo_by_id(self, user_repo_id: str) -> bool:
        """Delete user-repository association by ID"""
        try:
            UserRepository.objects.filter(id=user_repo_id).delete()
            logger.info(f"Deleted user-repo association ID: {user_repo_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting user repo by ID: {e}")
            return False
    
    def save_user_metrics(self, email: str, metrics: Dict[str, Any]) -> bool:
        """Save user metrics to database"""
        try:
            user = self.get_user_by_email(email)
            if not user:
                logger.error(f"User not found for email: {email}")
                return False
            
            today = timezone.now().date()
            
            with transaction.atomic():
                user_metrics, created = UserMetrics.objects.update_or_create(
                    user=user,
                    date=today,
                    defaults={
                        'total_commits': metrics.get('total_commits', 0),
                        'total_prs': metrics.get('total_prs', 0),
                        'total_issues': metrics.get('total_issues', 0),
                        'contributions_score': metrics.get('contributions_score', 0),
                        'repos_contributed': metrics.get('repos_contributed', 0),
                        'languages': metrics.get('languages', {}),
                        'activity_score': metrics.get('activity_score', 0),
                        'metrics_data': metrics  # Store complete metrics data
                    }
                )
                
                logger.info(f"{'Created' if created else 'Updated'} user metrics for {email}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving user metrics: {e}")
            return False
    
    def save_repo_metrics(self, repo_owner: str, repo_name: str, metrics: Dict[str, Any], user_session: Dict = None) -> bool:
        """Save repository metrics to database"""
        try:
            repo_full_name = f"{repo_owner}/{repo_name}"
            
            with transaction.atomic():
                # Get or create repository
                repo, created = Repository.objects.get_or_create(
                    full_name=repo_full_name,
                    defaults={
                        'owner': repo_owner,
                        'name': repo_name,
                        'description': metrics.get('description', ''),
                        'url': metrics.get('url', ''),
                        'language': metrics.get('language', ''),
                        'stargazers_count': metrics.get('stars', 0),
                        'forks_count': metrics.get('forks', 0)
                    }
                )
                
                today = timezone.now().date()
                
                # Save repository metrics
                repo_metrics, created = RepositoryMetrics.objects.update_or_create(
                    repository=repo,
                    date=today,
                    defaults={
                        'stars': metrics.get('stars', 0),
                        'forks': metrics.get('forks', 0),
                        'watchers': metrics.get('watchers', 0),
                        'issues': metrics.get('issues', 0),
                        'pull_requests': metrics.get('pull_requests', 0),
                        'contributors': metrics.get('contributors', 0),
                        'commits': metrics.get('commits', 0),
                        'releases': metrics.get('releases', 0),
                        'health_score': metrics.get('health_score', 0),
                        'activity_score': metrics.get('activity_score', 0),
                        'metrics_data': metrics
                    }
                )
                
                logger.info(f"{'Created' if created else 'Updated'} repo metrics for {repo_full_name}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving repo metrics: {e}")
            return False
    
    def get_user_metrics(self, user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Get user metrics history"""
        try:
            user = User.objects.get(id=user_id)
            metrics_qs = UserMetrics.objects.filter(user=user).order_by('-date')[:limit]
            
            metrics = []
            for metric in metrics_qs:
                data = {
                    'date': metric.date.isoformat(),
                    'total_commits': metric.total_commits,
                    'total_prs': metric.total_prs,
                    'total_issues': metric.total_issues,
                    'contributions_score': metric.contributions_score,
                    'repos_contributed': metric.repos_contributed,
                    'languages': metric.languages,
                    'activity_score': metric.activity_score,
                    'created_at': metric.created_at.isoformat(),
                    'updated_at': metric.updated_at.isoformat(),
                    'metric_timestamp': metric.metric_timestamp.isoformat(),
                }
                
                # Merge comprehensive metrics data
                if metric.metrics_data:
                    data.update(metric.metrics_data)
                    data['metrics_data'] = metric.metrics_data
                else:
                    data['metrics_data'] = data.copy()
                
                metrics.append(data)
            
            logger.info(f"Retrieved {len(metrics)} user metrics records")
            return metrics
            
        except User.DoesNotExist:
            logger.error(f"User not found: {user_id}")
            return []
        except Exception as e:
            logger.error(f"Error getting user metrics: {e}")
            return []
    
    def get_repo_metrics(self, repo_owner: str, repo_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get repository metrics history"""
        try:
            repo_full_name = f"{repo_owner}/{repo_name}"
            repo = Repository.objects.get(full_name=repo_full_name)
            
            metrics_qs = RepositoryMetrics.objects.filter(repository=repo).order_by('-date')[:limit]
            
            metrics = []
            for metric in metrics_qs:
                metrics.append({
                    'date': metric.date.isoformat(),
                    'stars': metric.stars,
                    'forks': metric.forks,
                    'watchers': metric.watchers,
                    'issues': metric.issues,
                    'pull_requests': metric.pull_requests,
                    'contributors': metric.contributors,
                    'commits': metric.commits,
                    'releases': metric.releases,
                    'health_score': metric.health_score,
                    'activity_score': metric.activity_score,
                    'created_at': metric.created_at.isoformat(),
                    'updated_at': metric.updated_at.isoformat(),
                    'metrics_data': metric.metrics_data
                })
            
            logger.info(f"Retrieved {len(metrics)} repo metrics records for {repo_full_name}")
            return metrics
            
        except Repository.DoesNotExist:
            logger.warning(f"Repository {repo_full_name} not found in database")
            return []
        except Exception as e:
            logger.error(f"Error getting repo metrics: {e}")
            return []