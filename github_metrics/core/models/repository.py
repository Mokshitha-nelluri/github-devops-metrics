from django.db import models


class Repository(models.Model):
    """Repository model for GitHub repositories"""
    owner = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    full_name = models.CharField(max_length=511, unique=True)
    description = models.TextField(null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    language = models.CharField(max_length=100, null=True, blank=True)
    stargazers_count = models.IntegerField(default=0)
    forks_count = models.IntegerField(default=0)
    is_private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name

    class Meta:
        db_table = 'repos'
        unique_together = ['owner', 'name']