from django.db import models
from django.contrib.auth.models import User

class Watchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watchlist')
    movie_title = models.CharField(max_length=255, default="Untitled")
    movie_year = models.CharField(max_length=10, blank=True, null=True)
    imdb_id = models.CharField(max_length=50, default='default_imdb_id')
    poster = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"{self.movie_title} ({self.movie_year}) - {self.user.username}"

    class Meta:
        verbose_name = 'Watchlist'
        verbose_name_plural = 'Watchlists'
        unique_together = ['user', 'imdb_id']  
