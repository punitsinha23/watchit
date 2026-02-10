import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'watchit.settings')
django.setup()

from watchit_app.models import WatchParty

def check_parties():
    parties = WatchParty.objects.all().order_by('-created_at')[:10]
    print(f"{'Room':<8} | {'IMDB ID':<12} | {'Title':<30} | {'Poster':<20}")
    print("-" * 80)
    for p in parties:
        title = p.movie_title or "EMPTY"
        poster = "YES" if p.poster_url else "NO"
        print(f"{p.room_code:<8} | {p.imdb_id:<12} | {title[:30]:<30} | {poster:<20}")

if __name__ == "__main__":
    check_parties()
