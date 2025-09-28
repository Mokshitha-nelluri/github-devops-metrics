"""
Setup database and initial data
Django management command for initial setup
"""
import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User as DjangoUser
from django.db import transaction

from core.models import User


class Command(BaseCommand):
    help = 'Initialize database and setup initial data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create Django superuser'
        )
        parser.add_argument(
            '--load-sample-data',
            action='store_true',
            help='Load sample data for testing'
        )
    
    def handle(self, *args, **options):
        """Main setup handler"""
        self.stdout.write(
            self.style.SUCCESS('Starting GitHub Metrics Setup')
        )
        
        # Run migrations
        self.stdout.write('Running database migrations...')
        call_command('migrate', verbosity=0)
        self.stdout.write(self.style.SUCCESS('✓ Database migrations completed'))
        
        # Create superuser if requested
        if options['create_superuser']:
            self.create_superuser()
        
        # Load sample data if requested
        if options['load_sample_data']:
            self.load_sample_data()
        
        self.stdout.write(
            self.style.SUCCESS('Setup completed successfully!')
        )
        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write('1. Set environment variables (GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET)')
        self.stdout.write('2. Start the development server: python manage.py runserver')
        self.stdout.write('3. Visit the API at http://localhost:8000/api/')
    
    def create_superuser(self):
        """Create Django superuser"""
        try:
            if not DjangoUser.objects.filter(is_superuser=True).exists():
                self.stdout.write('Creating superuser...')
                
                username = input('Superuser username (admin): ') or 'admin'
                email = input('Superuser email: ')
                
                if email:
                    superuser = DjangoUser.objects.create_superuser(
                        username=username,
                        email=email,
                        password='admin123'  # Default password
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Superuser created: {username}')
                    )
                    self.stdout.write(
                        self.style.WARNING('Default password: admin123 (change this!)')
                    )
                else:
                    self.stdout.write('Email required for superuser')
            else:
                self.stdout.write('Superuser already exists')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating superuser: {e}')
            )
    
    def load_sample_data(self):
        """Load sample data for testing"""
        try:
            self.stdout.write('Loading sample data...')
            
            with transaction.atomic():
                # Create sample user
                sample_user, created = User.objects.get_or_create(
                    email='test@example.com',
                    defaults={
                        'github_username': 'testuser',
                        'name': 'Test User',
                        'github_token': 'sample_token_for_testing'
                    }
                )
                
                if created:
                    self.stdout.write('✓ Sample user created: test@example.com')
                else:
                    self.stdout.write('Sample user already exists')
            
            self.stdout.write(self.style.SUCCESS('✓ Sample data loaded'))
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error loading sample data: {e}')
            )