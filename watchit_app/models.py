from django.db import models
from django.contrib.auth.models import User

class WatchParty(models.Model):
    room_code = models.CharField(max_length=6, unique=True)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_parties')
    imdb_id = models.CharField(max_length=20)
    movie_title = models.CharField(max_length=255, blank=True, null=True)
    poster_url = models.URLField(max_length=500, blank=True, null=True)
    current_season = models.IntegerField(default=1)
    current_episode = models.IntegerField(default=1)
    current_source = models.CharField(max_length=50, default='vidsrc')
    is_active = models.BooleanField(default=True)
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


