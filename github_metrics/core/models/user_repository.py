from django.db import models
from .user import User
from .repository import Repository


class UserRepository(models.Model):
    """Many-to-many relationship between users and repositories"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_repos')
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='user_repos')
    role = models.CharField(max_length=50, default='contributor')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} -> {self.repository.full_name}"

    class Meta:
        db_table = 'user_repos'
        unique_together = ['user', 'repository']