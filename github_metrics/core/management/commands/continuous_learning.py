"""
Continuous ML Learning Management Command
Handles background ML model training and updates
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from core.models import User
from analytics.ml import get_learning_system

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run continuous ML learning system to train and update user models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-email',
            type=str,
            help='Train model for specific user email'
        )
        parser.add_argument(
            '--force-retrain',
            action='store_true',
            help='Force retrain all models regardless of conditions'
        )
        parser.add_argument(
            '--cleanup-days',
            type=int,
            default=30,
            help='Clean up model files older than this many days'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it'
        )

    def handle(self, *args, **options):
        learning_system = get_learning_system()
        
        self.stdout.write(
            self.style.SUCCESS('Starting Continuous ML Learning System...')
        )
        
        user_email = options['user_email']
        force_retrain = options['force_retrain']
        cleanup_days = options['cleanup_days']
        dry_run = options['dry_run']
        
        if user_email:
            # Train model for specific user
            self._train_single_user(learning_system, user_email, force_retrain, dry_run)
        else:
            # Train models for all users who need it
            self._train_all_users(learning_system, force_retrain, dry_run)
        
        # Cleanup old models
        if not dry_run and cleanup_days > 0:
            self._cleanup_old_models(learning_system, cleanup_days)
            
        self.stdout.write(
            self.style.SUCCESS('Continuous ML Learning System completed!')
        )

    def _train_single_user(self, learning_system, user_email, force_retrain, dry_run):
        """Train model for a specific user"""
        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User not found: {user_email}')
            )
            return
            
        self.stdout.write(f'Processing user: {user_email}')
        
        # Check if retraining is needed
        if not force_retrain and not learning_system.should_retrain_model(user_email):
            self.stdout.write(f'  ✓ Model is up to date for {user_email}')
            return
            
        if dry_run:
            self.stdout.write(f'  [DRY RUN] Would retrain model for {user_email}')
            return
            
        # Train model
        success = learning_system.train_user_model(user_email)
        
        if success:
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ Successfully trained model for {user_email}')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'  ✗ Failed to train model for {user_email}')
            )

    def _train_all_users(self, learning_system, force_retrain, dry_run):
        """Train models for all users who need it"""
        users = User.objects.filter(github_token__isnull=False)
        
        self.stdout.write(f'Found {users.count()} users with GitHub tokens')
        
        trained_count = 0
        skipped_count = 0
        failed_count = 0
        
        for user in users:
            try:
                # Check if retraining is needed
                needs_training = force_retrain or learning_system.should_retrain_model(user.email)
                
                if not needs_training:
                    self.stdout.write(f'  ✓ Model up to date for {user.email}')
                    skipped_count += 1
                    continue
                    
                if dry_run:
                    self.stdout.write(f'  [DRY RUN] Would retrain model for {user.email}')
                    continue
                    
                self.stdout.write(f'  Training model for {user.email}...')
                
                # Train model
                success = learning_system.train_user_model(user.email)
                
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f'    ✓ Successfully trained model for {user.email}')
                    )
                    trained_count += 1
                else:
                    self.stdout.write(
                        self.style.ERROR(f'    ✗ Failed to train model for {user.email}')
                    )
                    failed_count += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error processing {user.email}: {e}')
                )
                failed_count += 1
                
        # Summary
        self.stdout.write('')
        self.stdout.write('Training Summary:')
        self.stdout.write(f'  Models trained: {trained_count}')
        self.stdout.write(f'  Models skipped: {skipped_count}')
        self.stdout.write(f'  Training failed: {failed_count}')

    def _cleanup_old_models(self, learning_system, cleanup_days):
        """Clean up old model files"""
        self.stdout.write(f'Cleaning up model files older than {cleanup_days} days...')
        
        try:
            deleted_count = learning_system.cleanup_old_models(cleanup_days)
            
            if deleted_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Deleted {deleted_count} old model files')
                )
            else:
                self.stdout.write('  ✓ No old model files to clean up')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ✗ Error during cleanup: {e}')
            )