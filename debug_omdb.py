# Debugging OMDb Response

import requests

api_key = 'bd268b10'
imdb_id = 'tt1375666' # Inception

url = f"http://www.omdbapi.com/?apikey={api_key}&i={imdb_id}&plot=full"
response = requests.get(url)
data = response.json()

print("Keys:", data.keys())
if 'tmdbID' in data:
    print("Found TMDB ID:", data['tmdbID'])
else:
    print("TMDB ID not found in OMDb response.")
