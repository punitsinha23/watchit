import os
import django
import requests

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'watchit.settings')
django.setup()

from watchit_app.models import WatchParty
from decouple import config

api_key = config('OMDB_API_KEY', default='24a15e19')

def backfill_metadata():
    parties = WatchParty.objects.filter(movie_title__isnull=True) | WatchParty.objects.filter(movie_title="")
    print(f"DEBUG: Found {parties.count()} parties to backfill.")
    
    for party in parties:
        print(f"DEBUG: Fetching for {party.imdb_id}...")
        try:
            res = requests.get(f"http://www.omdbapi.com/?i={party.imdb_id}&apikey={api_key}")
            if res.status_code == 200:
                data = res.json()
                party.movie_title = data.get('Title', '')
                party.poster_url = data.get('Poster', '')
                party.save()
                print(f"DEBUG: Updated {party.room_code} -> {party.movie_title}")
            else:
                print(f"DEBUG: API Error for {party.room_code}: {res.status_code}")
        except Exception as e:
            print(f"DEBUG: Error for {party.room_code}: {e}")

if __name__ == "__main__":
    backfill_metadata()
