from django.db import models
from django.contrib.auth.models import AbstractUser


class User(models.Model):
    """User model for GitHub metrics tracking"""
    email = models.EmailField(unique=True)
    github_username = models.CharField(max_length=255, null=True, blank=True)
    github_token = models.TextField(null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    avatar_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email

    class Meta:
        db_table = 'users'