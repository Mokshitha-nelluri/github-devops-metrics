"""
Background metrics refresh service
Django management command version of background_metrics_service.py
"""
import time
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from core.models import User, UserRepository
from core.services import DataService, GitHubService, MetricsService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Background metrics refresh service for all users'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=str,
            help='Comma-separated list of user emails to process (default: all users)'
        )
        parser.add_argument(
            '--max-workers',
            type=int,
            default=3,
            help='Maximum number of concurrent workers (default: 3)'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=3600,
            help='Refresh interval in seconds (default: 3600 = 1 hour)'
        )
        parser.add_argument(
            '--run-once',
            action='store_true',
            help='Run once and exit (default: continuous mode)'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        self.stdout.write(
            self.style.SUCCESS('Starting GitHub Metrics Background Refresh Service')
        )
        
        max_workers = options['max_workers']
        interval = options['interval']
        run_once = options['run_once']
        user_filter = options.get('users')
        
        if user_filter:
            user_emails = [email.strip() for email in user_filter.split(',')]
            self.stdout.write(f'Processing specific users: {user_emails}')
        else:
            user_emails = None
            self.stdout.write('Processing all users with GitHub tokens')
        
        if run_once:
            self.stdout.write('Running in single-execution mode')
            self.refresh_all_users(user_emails, max_workers)
        else:
            self.stdout.write(f'Running in continuous mode (interval: {interval}s)')
            self.run_continuous(user_emails, max_workers, interval)
    
    def run_continuous(self, user_emails, max_workers, interval):
        """Run continuous background refresh"""
        try:
            while True:
                start_time = time.time()
                
                self.stdout.write(
                    f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                    'Starting metrics refresh cycle'
                )
                
                try:
                    self.refresh_all_users(user_emails, max_workers)
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error in refresh cycle: {e}')
                    )
                    logger.error(f'Background refresh error: {e}')
                
                # Calculate next run time
                elapsed_time = time.time() - start_time
                sleep_time = max(0, interval - elapsed_time)
                
                if sleep_time > 0:
                    self.stdout.write(
                        f'Refresh cycle completed in {elapsed_time:.1f}s. '
                        f'Sleeping for {sleep_time:.1f}s until next cycle'
                    )
                    time.sleep(sleep_time)
                else:
                    self.stdout.write(
                        f'Refresh cycle took {elapsed_time:.1f}s '
                        f'(longer than interval {interval}s)'
                    )
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.SUCCESS('Background service stopped by user')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Fatal error in background service: {e}')
            )
            logger.error(f'Fatal background service error: {e}')
    
    def refresh_all_users(self, user_emails, max_workers):
        """Refresh metrics for all users"""
        try:
            # Get users to process
            users_query = User.objects.exclude(github_token__isnull=True).exclude(github_token='')
            
            if user_emails:
                users_query = users_query.filter(email__in=user_emails)
            
            users = list(users_query.select_related())
            
            if not users:
                self.stdout.write('No users with GitHub tokens found')
                return
            
            self.stdout.write(f'Processing {len(users)} users with {max_workers} workers')
            
            # Process users concurrently
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_user = {
                    executor.submit(self.refresh_user_metrics, user): user 
                    for user in users
                }
                
                completed = 0
                errors = 0
                
                for future in as_completed(future_to_user):
                    user = future_to_user[future]
                    completed += 1
                    
                    try:
                        success = future.result()
                        if success:
                            self.stdout.write(
                                f'[{completed}/{len(users)}] ✓ {user.email}'
                            )
                        else:
                            self.stdout.write(
                                f'[{completed}/{len(users)}] ✗ {user.email} (failed)'
                            )
                            errors += 1
                    except Exception as e:
                        self.stdout.write(
                            f'[{completed}/{len(users)}] ✗ {user.email} (error: {e})'
                        )
                        errors += 1
                        logger.error(f'Error refreshing user {user.email}: {e}')
            
            success_count = len(users) - errors
            self.stdout.write(
                self.style.SUCCESS(
                    f'Refresh completed: {success_count} successful, {errors} errors'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error in refresh_all_users: {e}')
            )
            logger.error(f'Background refresh error: {e}')
    
    def refresh_user_metrics(self, user):
        """Refresh metrics for a single user"""
        try:
            # Check if user needs refresh (avoid too frequent updates)
            latest_metrics = user.metrics.order_by('-created_at').first()
            if latest_metrics:
                time_since_last = timezone.now() - latest_metrics.created_at
                if time_since_last < timedelta(hours=1):
                    # Skip if updated less than 1 hour ago
                    return True
            
            # Get user repositories
            user_repos = UserRepository.objects.filter(user=user).select_related('repository')
            
            if not user_repos.exists():
                logger.info(f'No repositories for user {user.email}')
                return True
            
            # Initialize services
            github_service = GitHubService(user.github_token)
            metrics_service = MetricsService()
            data_service = DataService()
            
            # Collect data from all repositories
            all_commits = []
            all_prs = []
            
            for user_repo in user_repos:
                repo = user_repo.repository
                
                try:
                    # Fetch data (limit to recent activity to avoid rate limits)
                    commits = github_service.fetch_commits(
                        repo.owner, repo.name, user.email, days_back=30
                    )
                    prs = github_service.fetch_pull_requests(
                        repo.owner, repo.name, user.email, days_back=30
                    )
                    
                    all_commits.extend(commits)
                    all_prs.extend(prs)
                    
                except Exception as e:
                    logger.warning(f'Failed to fetch data for {repo.full_name}: {e}')
                    continue
            
            # Calculate metrics
            metrics = metrics_service.calculate_all_metrics(
                all_commits, all_prs, 'tracked'
            )
            
            # Save metrics
            success = data_service.save_user_metrics(user.email, metrics)
            
            if success:
                logger.info(f'Updated metrics for {user.email}: {len(all_commits)} commits, {len(all_prs)} PRs')
            
            return success
            
        except Exception as e:
            logger.error(f'Error refreshing metrics for user {user.email}: {e}')
            return False