from django.shortcuts import render,redirect
import json
import random
import requests
from .data import keyword, shows, top_100_movies, animes , anime_ids
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.core.cache import cache

from decouple import config

api_key = config('OMDB_API_KEY', default='bd268b10')

def fetch_omdb_data(imdb_id=None, title=None, season=None):
    """
    Helper to fetch data from OMDb API with caching.
    """
    raw_key = f"omdb_{imdb_id or title}_{season or 'main'}"
    cache_key = raw_key.replace(" ", "_")
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    if imdb_id:
        url = f"http://www.omdbapi.com/?apikey={api_key}&i={imdb_id}&plot=full"
        if season:
            url += f"&Season={season}"
    elif title:
        url = f"http://www.omdbapi.com/?apikey={api_key}&t={title}"
    else:
        return None

    try:
        response = requests.get(url, timeout=5)
        print(f"OMDB API Response Status: {response.status_code} for URL: {url}")
        if response.status_code == 200:
            data = response.json()
            print(f"OMDB API Response: {data.get('Response')}, Error: {data.get('Error', 'None')}")
            if data.get("Response") == "True":
                # Cache for 24 hours
                cache.set(cache_key, data, 86400)
                return data
    except Exception as e:
        print(f"OMDB API Exception: {e}")
        pass
    return None

def base(request):
    # Limit homepage items to 15 to save API calls
    LIMIT = 15
    
    movies = []
    for title in keyword[:LIMIT]:
        data = fetch_omdb_data(title=title)
        if data:
            movies.append(data)
    
    shows_list = []
    for title in shows[:LIMIT]:
        data = fetch_omdb_data(title=title)
        if data:
            shows_list.append(data)

    Animes = []
    for title in animes[:LIMIT]:
        data = fetch_omdb_data(title=title)
        if data:
            Animes.append(data)            

    context = {
        'movies': movies,
        'shows' : shows_list,
        'Animes': Animes,
    }
    return render(request, 'base.html', context)

def dashboard(request):
    movie_data = None
    error = None

    if request.method == "POST":
        movie_title = request.POST.get('title')

        if not movie_title:
            error = "Please enter a movie title."
            return render(request, 'dashboard.html', {'movie_data': movie_data, 'error': error})

        # Search results are also cached by query
        cache_key = f"search_{movie_title.lower()}".replace(" ", "_")
        cached_results = cache.get(cache_key)
        
        if cached_results:
            movie_data = cached_results
        else:
            try:
                api_url = f"http://www.omdbapi.com/?apikey={api_key}&s={movie_title}"  
                response = requests.get(api_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("Response") == "True":
                        movie_data = data.get("Search", [])
                        cache.set(cache_key, movie_data, 3600) # Cache search for 1 hour
                    else:
                        error = data.get("Error", "No movies or series found matching the title.")
                else:
                    error = "Failed to fetch data from OMDb API. Please try again later."
            except Exception as e:
                error = f"An error occurred: {str(e)}"

    return render(request, 'dashboard.html', {'movie_data': movie_data, 'error': error})

def movie_view(request):
    movies_per_page = 28
    page_number = request.GET.get('page', 1)
    paginator = Paginator(top_100_movies, movies_per_page)
    page_obj = paginator.get_page(page_number)

    movies = []
    for movie_id in page_obj.object_list:
        data = fetch_omdb_data(imdb_id=movie_id)
        if data:
            movies.append(data)

    return render(request, 'movies.html', {'page_obj': page_obj, 'movies': movies})

def anime_view(request):
    movies_per_page = 20
    page_number = request.GET.get('page', 1)
    paginator = Paginator(anime_ids, movies_per_page)
    page_obj = paginator.get_page(page_number)

    animes = []
    for id in page_obj.object_list:
        data = fetch_omdb_data(imdb_id=id)
        if data:
            animes.append(data)
    
    return render(request, 'anime.html', {'page_obj': page_obj, 'animes': animes})

def shows_view(request):
    items_per_page = 20
    page_number = request.GET.get('page', 1)
    paginator = Paginator(shows, items_per_page)
    page_obj = paginator.get_page(page_number)

    shows_list = []
    for title in page_obj.object_list:
        data = fetch_omdb_data(title=title)
        if data:
            shows_list.append(data)
    
    return render(request, 'shows.html', {'page_obj': page_obj, 'shows': shows_list})

def about_view(request):
    return render(request , 'about.html')    

def detail_view(request, imdb_id):
    print(f"Attempting to fetch movie data for IMDB ID: {imdb_id}")
    movie_data = fetch_omdb_data(imdb_id=imdb_id)
    print(f"Movie data received: {movie_data is not None}")
    if not movie_data:
        # Fallback or redirect if movie not found
        print(f"No movie data found for {imdb_id}, redirecting to base")
        return redirect('base')
    
    season_data = {}
    if movie_data.get('Type') == 'series':
        season_data = fetch_omdb_data(imdb_id=imdb_id, season=1) or {}
            
    # Recommendations (Random selection from existing lists)
    recommendations = []
    # Combine lists and pick random 12
    all_recs = top_100_movies + anime_ids
    random_ids = random.sample(all_recs, min(len(all_recs), 12))
    
    for rec_id in random_ids:
        data = fetch_omdb_data(imdb_id=rec_id)
        if data and data.get('Poster') != 'N/A':
            recommendations.append(data)

    context = {
        'movie': movie_data,
        'season_data': season_data,
        'episodes_json': json.dumps(season_data.get('Episodes', [])),
        'recommendations': recommendations,
        'api_key': api_key
    }
    return render(request, 'detail.html', context)

def fetch_more_items(request):
    """
    API endpoint for horizontal infinite scrolling.
    """
    category = request.GET.get('category')
    page = int(request.GET.get('page', 1))
    
    if category == 'movies':
        all_items = top_100_movies
        items_per_page = 28
        use_id = True
    elif category == 'anime':
        all_items = anime_ids
        items_per_page = 20
        use_id = True
    elif category == 'shows':
        all_items = shows
        items_per_page = 20
        use_id = False
    elif category == 'popular_movies':
        all_items = keyword
        items_per_page = 15
        use_id = False
    elif category == 'home_shows':
        all_items = shows
        items_per_page = 15
        use_id = False
    elif category == 'popular_anime':
        all_items = animes
        items_per_page = 15
        use_id = False
    else:
        return JsonResponse({'error': 'Invalid category'}, status=400)

    start = (page - 1) * items_per_page
    end = start + items_per_page
    current_items = all_items[start:end]
    
    items = []
    for item in current_items:
        if use_id:
            data = fetch_omdb_data(imdb_id=item)
        else:
            data = fetch_omdb_data(title=item)
             
        if data and data.get('Poster') != 'N/A':
            items.append({
                'imdbID': data.get('imdbID'),
                'Title': data.get('Title'),
                'Poster': data.get('Poster'),
                'Year': data.get('Year'),
            })
            
    return JsonResponse({
        'items': items,
        'has_next': end < len(all_items)
    })
