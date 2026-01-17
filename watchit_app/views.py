from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
import json
import random
import requests

from .data import keyword, shows, top_100_movies, animes, anime_ids
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.core.cache import cache
from django.views.decorators.cache import cache_control
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
        if response.status_code == 200:
            data = response.json()
            if data.get("Response") == "True":
                cache.set(cache_key, data, 86400)  # 24 hours
                return data
    except Exception:
        pass
        
    # Mock Data Fallback (API Limit Reached)
    # Generate deterministic mock data based on input
    mock_id = imdb_id or f"tt{hash(title or 'unknown') % 10000000}"
    mock_title = title or "Mock Title"
    return {
        "Title": mock_title,
        "Year": "2024",
        "imdbID": mock_id,
        "Type": "movie",
        "Poster": "https://via.placeholder.com/300x450.png?text=" + mock_title.replace(" ", "+"),
        "Plot": "This is a placeholder plot because the OMDB API limit was reached.",
        "Response": "True"
    }


@cache_control(private=True, max_age=3600)
def base(request):
    LIMIT = 15
    print("DEBUG: Fetching base view data...")
    
    # Debug fetch_omdb_data for first item
    if keyword:
        print(f"DEBUG: First keyword: {keyword[0]}")
        test_res = fetch_omdb_data(title=keyword[0])
        print(f"DEBUG: Result for {keyword[0]}: {test_res}")

    movies = [fetch_omdb_data(title=t) for t in keyword[:LIMIT] if fetch_omdb_data(title=t)]
    print(f"DEBUG: Movies count: {len(movies)}")
    
    shows_list = [fetch_omdb_data(title=t) for t in shows[:LIMIT] if fetch_omdb_data(title=t)]
    print(f"DEBUG: Shows count: {len(shows_list)}")
    
    anime_list = [fetch_omdb_data(title=t) for t in animes[:LIMIT] if fetch_omdb_data(title=t)]
    print(f"DEBUG: Anime count: {len(anime_list)}")

    return render(request, 'base.html', {
        'movies': movies,
        'shows': shows_list,
        'Animes': anime_list,
    })


@login_required
@cache_control(private=True, max_age=3600)
def dashboard(request):
    movie_data = None
    error = None

    if request.method == "POST":
        movie_title = request.POST.get('title')

        if not movie_title:
            error = "Please enter a movie title."
            return render(request, 'dashboard.html', {'movie_data': movie_data, 'error': error})

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
                        cache.set(cache_key, movie_data, 3600)  # 1 hour
                    else:
                        error = data.get("Error", "No results found.")
                else:
                    error = "Failed to fetch data from OMDb API."
            except Exception as e:
                error = f"An error occurred: {str(e)}"

    return render(request, 'dashboard.html', {'movie_data': movie_data, 'error': error})


@login_required
def movie_view(request):
    paginator = Paginator(top_100_movies, 28)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    movies = [fetch_omdb_data(imdb_id=i) for i in page_obj.object_list if fetch_omdb_data(imdb_id=i)]

    return render(request, 'movies.html', {'page_obj': page_obj, 'movies': movies})


@login_required
def anime_view(request):
    paginator = Paginator(anime_ids, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    animes_list = [fetch_omdb_data(imdb_id=i) for i in page_obj.object_list if fetch_omdb_data(imdb_id=i)]

    return render(request, 'anime.html', {'page_obj': page_obj, 'animes': animes_list})


@login_required
def shows_view(request):
    paginator = Paginator(shows, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    shows_list = [fetch_omdb_data(title=t) for t in page_obj.object_list if fetch_omdb_data(title=t)]

    return render(request, 'shows.html', {'page_obj': page_obj, 'shows': shows_list})


def about_view(request):
    return render(request, 'about.html')


@login_required
@cache_control(private=True, max_age=3600)
def detail_view(request, imdb_id):
    movie_data = fetch_omdb_data(imdb_id=imdb_id)
    if not movie_data:
        return redirect('base')

    season_data = {}
    if movie_data.get('Type') == 'series':
        season_data = fetch_omdb_data(imdb_id=imdb_id, season=1) or {}

    all_recs = top_100_movies + anime_ids
    recommendations = []

    for rec_id in random.sample(all_recs, min(len(all_recs), 12)):
        data = fetch_omdb_data(imdb_id=rec_id)
        if data and data.get('Poster') != 'N/A':
            recommendations.append(data)

    return render(request, 'detail.html', {
        'movie': movie_data,
        'season_data': season_data,
        'episodes_json': json.dumps(season_data.get('Episodes', [])),
        'recommendations': recommendations,
        'api_key': api_key
    })


def fetch_more_items(request):
    category = request.GET.get('category')
    page = int(request.GET.get('page', 1))

    config_map = {
        'movies': (top_100_movies, 28, True),
        'anime': (anime_ids, 20, True),
        'shows': (shows, 20, False),
        'popular_movies': (keyword, 15, False),
        'home_shows': (shows, 15, False),
        'popular_anime': (animes, 15, False),
    }

    if category not in config_map:
        return JsonResponse({'error': 'Invalid category'}, status=400)

    all_items, per_page, use_id = config_map[category]
    start, end = (page - 1) * per_page, page * per_page

    items = []
    from django.urls import reverse

    is_authenticated = request.user.is_authenticated
    login_url = reverse('login')

    for item in all_items[start:end]:
        data = fetch_omdb_data(imdb_id=item if use_id else None, title=None if use_id else item)
        if data and data.get('Poster') != 'N/A':
            imdb_id = data.get('imdbID')
            destination_url = reverse('detail', args=[imdb_id]) if is_authenticated else login_url

            items.append({
                'imdbID': imdb_id,
                'Title': data.get('Title'),
                'Poster': data.get('Poster'),
                'Year': data.get('Year'),
                'url': destination_url
            })

    return JsonResponse({'items': items, 'has_next': end < len(all_items)})
