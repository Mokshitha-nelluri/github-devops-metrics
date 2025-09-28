from django.db import models
try:
    from django.contrib.postgres.fields import JSONField
except ImportError:
    # Fallback for SQLite/other databases
    JSONField = models.JSONField
from .user import User
from .repository import Repository


class UserMetrics(models.Model):
    """User metrics model for storing calculated metrics"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='metrics')
    date = models.DateField()
    total_commits = models.IntegerField(default=0)
    total_prs = models.IntegerField(default=0)
    total_issues = models.IntegerField(default=0)
    contributions_score = models.FloatField(default=0.0)
    repos_contributed = models.IntegerField(default=0)
    languages = JSONField(default=dict)
    activity_score = models.FloatField(default=0.0)
    metrics_data = JSONField(default=dict)  # Store comprehensive metrics
    metric_timestamp = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.date}"

    class Meta:
        db_table = 'metrics_user'
        unique_together = ['user', 'date']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['date']),
        ]


class RepositoryMetrics(models.Model):
    """Repository metrics model for storing repository-specific metrics"""
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='metrics')
    date = models.DateField()
    stars = models.IntegerField(default=0)
    forks = models.IntegerField(default=0)
    watchers = models.IntegerField(default=0)
    issues = models.IntegerField(default=0)
    pull_requests = models.IntegerField(default=0)
    contributors = models.IntegerField(default=0)
    commits = models.IntegerField(default=0)
    releases = models.IntegerField(default=0)
    health_score = models.FloatField(default=0.0)
    activity_score = models.FloatField(default=0.0)
    metrics_data = JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.repository.full_name} - {self.date}"

    class Meta:
        db_table = 'metrics_repo'
        unique_together = ['repository', 'date']
        indexes = [
            models.Index(fields=['repository', 'date']),
            models.Index(fields=['date']),
        ]