from django.db import models
from django.contrib.auth.models import User

class WatchParty(models.Model):
    room_code = models.CharField(max_length=6, unique=True)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_parties')
    imdb_id = models.CharField(max_length=20)
    movie_title = models.CharField(max_length=255, blank=True, null=True)
    movie_type = models.CharField(max_length=20, default='movie')
    poster_url = models.URLField(max_length=500, blank=True, null=True)
    total_seasons = models.IntegerField(default=0)
    current_season = models.IntegerField(default=1)
    current_episode = models.IntegerField(default=1)
    current_source = models.CharField(max_length=50, default='embedmaster')
    is_active = models.BooleanField(default=True)
    is_private = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    participants = models.ManyToManyField(User, related_name='joined_parties', blank=True)
    pending_participants = models.ManyToManyField(User, related_name='pending_parties', blank=True)

    def __str__(self):
        return f"Room {self.room_code} (Host: {self.host.username})"

class PartyMessage(models.Model):
    party = models.ForeignKey(WatchParty, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.text[:20]}"

class EpisodeRating(models.Model):
    show_id = models.CharField(max_length=50)  # TMDB show ID
    season_number = models.IntegerField()
    episode_number = models.IntegerField()
    episode_name = models.CharField(max_length=255)
    rating = models.DecimalField(max_digits=4, decimal_places=2)
    vote_count = models.IntegerField()
    air_date = models.DateField(null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('show_id', 'season_number', 'episode_number')
        ordering = ['season_number', 'episode_number']

    def __str__(self):
        return f"S{self.season_number}E{self.episode_number} - {self.episode_name}"


class ShowMapping(models.Model):
    """Cache IMDB ID to TMDB ID mapping so we don't need API calls on every page load."""
    imdb_id = models.CharField(max_length=20, unique=True)
    tmdb_id = models.CharField(max_length=50)
    show_name = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.imdb_id} -> {self.tmdb_id} ({self.show_name})"
