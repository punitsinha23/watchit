import requests
from django.conf import settings
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'watchit.settings')
django.setup()

from decouple import config

api_key = config('OMDB_API_KEY', default='593db72e')
imdb_id = 'tt1234567' # Sample IMDb ID

print(f"DEBUG: Testing with API Key: {api_key}")
try:
    url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={api_key}"
    print(f"DEBUG: URL: {url}")
    res = requests.get(url)
    print(f"DEBUG: Status Code: {res.status_code}")
    print(f"DEBUG: Response: {res.text}")
except Exception as e:
    print(f"DEBUG: Error: {e}")
