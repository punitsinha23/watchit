from django.db import models
from django.contrib.auth.models import User
import uuid

class Watchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    imdb_id = models.CharField(max_length=20)
    movie_title = models.CharField(max_length=255)
    movie_year = models.CharField(max_length=10, blank=True, null=True)
    poster = models.URLField(max_length=500, blank=True, null=True)
    added_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'imdb_id')
        ordering = ['-added_on']

    def __str__(self):
        return f"{self.user.username} - {self.movie_title}"


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"Reset token for {self.user.username}"
