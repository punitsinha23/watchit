from django.shortcuts import render, redirect
from account_app.models import Watchlist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
import json
import random
import requests
import time
from django.utils import timezone

from .data import keyword, shows, top_100_movies, animes, anime_ids
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.core.cache import cache
from django.views.decorators.cache import cache_control
from decouple import config
from .models import WatchParty, PartyMessage
import uuid
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt

api_key = config('OMDB_KEY', default='bd268b10')
api_key_2 = config('OMDB_KEY_2', default='24a15e19')

# ... (Previous constants)

@login_required
def create_watch_party(request, imdb_id):
    # 1. Handle Privacy Selection
    is_private_str = request.GET.get('is_private', 'true').lower()
    is_private = is_private_str == 'true'

    # 2. Create a unique 6-character room code
    while True:
        room_code = str(uuid.uuid4())[:6].upper()
        if not WatchParty.objects.filter(room_code=room_code).exists():
            break
            
    # Use the robust fetch_omdb_data helper
    movie_data = fetch_omdb_data(imdb_id=imdb_id)
    movie_title = movie_data.get('Title', '')
    poster_url = movie_data.get('Poster', '')

    party = WatchParty.objects.create(
        room_code=room_code,
        host=request.user,
        imdb_id=imdb_id,
        movie_title=movie_title,
        poster_url=poster_url,
        current_season=1,
        current_episode=1,
        is_private=is_private
    )
    return redirect('party_room', room_code=room_code)

@login_required
def join_watch_party(request):
    public_parties = WatchParty.objects.filter(is_active=True, is_private=False).exclude(host=request.user).order_by('-created_at')
    
    if request.method == 'POST':
        room_code = request.POST.get('room_code', '').upper()
        try:
            party = WatchParty.objects.get(room_code=room_code, is_active=True)
            
            # 24hr expiration check
            if (timezone.now() - party.created_at).total_seconds() > 86400:
                party.delete()
                return render(request, 'join_party.html', {
                    'error': 'This room has expired after 24 hours.',
                    'public_parties': public_parties
                })

            # If already a participant or the host, go straight in
            if request.user == party.host or party.participants.filter(id=request.user.id).exists():
                return redirect('party_room', room_code=room_code)
            
            # Add to pending if not already there
            if not party.pending_participants.filter(id=request.user.id).exists():
                party.pending_participants.add(request.user)
            
            return redirect('waiting_room', room_code=room_code)
        except WatchParty.DoesNotExist:
            return render(request, 'join_party.html', {
                'error': 'Invalid or inactive room code',
                'public_parties': public_parties
            })
    return render(request, 'join_party.html', {'public_parties': public_parties})

@login_required
def waiting_room(request, room_code):
    try:
        party = WatchParty.objects.get(room_code=room_code, is_active=True)
        # 24hr expiration check
        if (timezone.now() - party.created_at).total_seconds() > 86400:
            party.delete()
            return redirect('base')
        
        # Add to pending if for some reason they are not there and not host/participant
        if request.user != party.host and not party.participants.filter(id=request.user.id).exists():
            if not party.pending_participants.filter(id=request.user.id).exists():
                party.pending_participants.add(request.user)
            
    except WatchParty.DoesNotExist:
        return redirect('base')
        
    if request.user == party.host or party.participants.filter(id=request.user.id).exists():
        return redirect('party_room', room_code=room_code)
        
    return render(request, 'waiting_room.html', {'party': party})

@login_required
def api_check_approval(request, room_code):
    try:
        party = WatchParty.objects.get(room_code=room_code, is_active=True)
        # 24hr expiration check
        if (timezone.now() - party.created_at).total_seconds() > 86400:
            party.delete()
            return JsonResponse({'status': 'room_gone'})
    except WatchParty.DoesNotExist:
        return JsonResponse({'status': 'room_gone'})
        
    if party.participants.filter(id=request.user.id).exists():
        return JsonResponse({'status': 'approved'})
    
    if not party.pending_participants.filter(id=request.user.id).exists():
        return JsonResponse({'status': 'denied'})
        
    return JsonResponse({'status': 'pending'})


@login_required
def party_room(request, room_code):
    try:
        party = WatchParty.objects.get(room_code=room_code, is_active=True)
        # 24hr expiration check
        if (timezone.now() - party.created_at).total_seconds() > 86400:
            party.delete()
            return redirect('base')
    except WatchParty.DoesNotExist:
        return redirect('base')

    # Access check: Host or Participant only
    if request.user != party.host and not party.participants.filter(id=request.user.id).exists():
        return redirect('waiting_room', room_code=room_code)


    # Fetch movie data using existing helper
    movie_data = fetch_omdb_data(imdb_id=party.imdb_id)
    if not movie_data:
        return redirect('base')

    season_data = {}
    if movie_data.get('Type') == 'series':
        season_data = fetch_omdb_data(imdb_id=party.imdb_id, season=party.current_season) or {}
    
    # Simple recommendation logic (can share with detail view)
    all_recs = top_100_movies + anime_ids
    recommendations = []
    # (Optional: Recommendations logic similar to detail_view, omitted for brevity if needed)

    return render(request, 'watch_party.html', {
        'party': party,
        'movie': movie_data,
        'season_data': season_data,
        'episodes_json': json.dumps(season_data.get('Episodes', [])),
        'is_host': request.user == party.host,
        'api_key': api_key
    })

def api_party_status(request, room_code):
    try:
        party = WatchParty.objects.get(room_code=room_code, is_active=True)
    except WatchParty.DoesNotExist:
        return JsonResponse({'error': 'Party not found'}, status=404)

    # Fetch messages since 'last_msg_id' if provided
    last_msg_id = request.GET.get('last_msg_id', 0)
    messages = party.messages.filter(id__gt=last_msg_id).order_by('timestamp')
    
    msgs_data = [{
        'id': m.id,
        'user': m.user.username,
        'text': m.text,
        'timestamp': m.timestamp.strftime('%H:%M')
    } for m in messages]

    # Viewer tracking
    current_time = time.time()
    v_cache_key = f"viewers_{room_code}"
    # Structure: {user_id: last_heartbeat_timestamp}
    viewers_map = cache.get(v_cache_key, {})
    
    # Update current user
    if request.user.is_authenticated:
        viewers_map[str(request.user.id)] = current_time
    
    # Clean up old viewers (inactive for > 15 seconds)
    active_viewers_map = {uid: ts for uid, ts in viewers_map.items() if current_time - ts < 15}
    cache.set(v_cache_key, active_viewers_map, 30) # short TTL
    
    viewer_count = len(active_viewers_map)

    return JsonResponse({
        'season': party.current_season,
        'episode': party.current_episode,
        'source': party.current_source,
        'messages': msgs_data,
        'viewers': viewer_count,
        'pending_users': [{'id': u.id, 'username': u.username} for u in party.pending_participants.all()] if request.user == party.host else []
    })

@csrf_exempt
@login_required
def api_handle_join_request(request, room_code):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        party = WatchParty.objects.get(room_code=room_code, is_active=True, host=request.user)
    except WatchParty.DoesNotExist:
        return JsonResponse({'error': 'Party not found or unauthorized'}, status=404)

    data = json.loads(request.body)
    user_id = data.get('user_id')
    action = data.get('action') # 'approve' or 'deny'
    
    try:
        user_to_handle = User.objects.get(id=user_id)
        party.pending_participants.remove(user_to_handle)
        if action == 'approve':
            party.participants.add(user_to_handle)
        return JsonResponse({'status': 'ok'})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

@csrf_exempt
@login_required
def delete_party(request, room_code):
    try:
        party = WatchParty.objects.get(room_code=room_code, host=request.user)
        party.delete()
        return redirect('user') 
    except WatchParty.DoesNotExist:
        return redirect('base')


@csrf_exempt
@login_required
def api_party_update(request, room_code):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        party = WatchParty.objects.get(room_code=room_code, is_active=True)
    except WatchParty.DoesNotExist:
        return JsonResponse({'error': 'Party not found'}, status=404)

    if request.user != party.host:
        return JsonResponse({'error': 'Only host can update settings'}, status=403)

    data = json.loads(request.body)
    party.current_season = data.get('season', party.current_season)
    party.current_episode = data.get('episode', party.current_episode)
    party.current_source = data.get('source', party.current_source)
    party.save()
    
    return JsonResponse({'status': 'ok'})

@csrf_exempt
@login_required
def api_party_chat(request, room_code):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        party = WatchParty.objects.get(room_code=room_code, is_active=True)
    except WatchParty.DoesNotExist:
        return JsonResponse({'error': 'Party not found'}, status=404)

    data = json.loads(request.body)
    text = data.get('text', '').strip()
    if text:
        PartyMessage.objects.create(party=party, user=request.user, text=text)

    return JsonResponse({'status': 'ok'})


# Free trial duration in seconds (45 minutes)
TRIAL_DURATION = 45 * 60  # 2700 seconds


def fetch_omdb_data(imdb_id=None, title=None, season=None):
    """
    Helper to fetch data from OMDb API with caching and database fallback.
    """
    # 1. Check Cache First
    raw_key = f"omdb_{imdb_id or title}_{season or 'main'}"
    cache_key = raw_key.replace(" ", "_")
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    # 2. Check Database for existing metadata (if it's a main fetch)
    if not season:
        existing_party = None
        if imdb_id:
            existing_party = WatchParty.objects.filter(imdb_id=imdb_id).exclude(movie_title="").exclude(movie_title__isnull=True).first()
        elif title:
            existing_party = WatchParty.objects.filter(movie_title__icontains=title).exclude(poster_url="").first()
        
        if existing_party:
            db_data = {
                "Title": existing_party.movie_title,
                "Poster": existing_party.poster_url,
                "imdbID": existing_party.imdb_id,
                "Response": "True"
            }
            cache.set(cache_key, db_data, 86400)
            return db_data

    # 3. Fetch from API
    keys_to_try = [api_key, api_key_2]
    
    for current_key in keys_to_try:
        if imdb_id:
            url = f"http://www.omdbapi.com/?apikey={current_key}&i={imdb_id}&plot=full"
            if season:
                url += f"&Season={season}"
        elif title:
            url = f"http://www.omdbapi.com/?apikey={current_key}&t={title}"
        else:
            return None

        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("Response") == "True":
                    cache.set(cache_key, data, 86400)  # 24 hours
                    return data
                else:
                    error_msg = data.get("Error", "")
                    print(f"DEBUG: OMDB API Error for {imdb_id or title} with key {current_key[:4]}...: {error_msg}")
                    # If it's a limit or key issue, try the next key
                    if "limit" in error_msg.lower() or "key" in error_msg.lower():
                        continue
                    else:
                        break # Other errors (not found, etc) shouldn't trigger failover
            elif response.status_code == 401:
                print(f"DEBUG: OMDB 401 Unauthorized for key {current_key[:4]}...")
                continue # Try next key
        except Exception as e:
            print(f"DEBUG: OMDB Fetch Exception for key {current_key[:4]}...: {e}")
            continue
        
    # 4. Final Mock Data Fallback (Last resort)
    mock_id = imdb_id or f"tt{hash(title or 'unknown') % 10000000}"
    mock_title = title or "Mock Title"

    return {
        "Title": mock_title,
        "Year": "2024",
        "imdbID": mock_id,
        "Type": "movie",
        "Poster": "https://via.placeholder.com/300x450.png?text=" + mock_title.replace(" ", "+"),
        "Plot": "Live data currently unavailable.",
        "Response": "True"
    }


# Recent releases (2023-2024) - 50 movies
recent_releases = [
    "Oppenheimer", "Barbie", "Dune: Part Two", "Poor Things", 
    "The Holdovers", "Killers of the Flower Moon", "Past Lives",
    "Anatomy of a Fall", "The Zone of Interest", "Ferrari",
    "The Boy and the Heron", "Saltburn", "All of Us Strangers",
    "May December", "The Iron Claw", "Maestro", "The Beekeeper",
    "Mean Girls", "Dream Scenario", "The Color Purple", "American Fiction",
    "Priscilla", "The Wonderful Story of Henry Sugar", "Society of the Snow",
    "The Teachers' Lounge", "Fallen Leaves", "Perfect Days",
    "Drive-Away Dolls", "Love Lies Bleeding", "Immaculate",
    "Civil War", "Late Night with the Devil", "Abigail",
    "The Fall Guy", "IF", "Furiosa: A Mad Max Saga",
    "Hit Man", "Bad Boys: Ride or Die", "Inside Out 2",
    "A Quiet Place: Day One", "Longlegs", "Deadpool & Wolverine",
    "Trap", "Alien: Romulus", "Blink Twice",
    "Beetlejuice Beetlejuice", "The Substance", "Speak No Evil",
    "Megalopolis", "The Wild Robot", "Smile 2"
]

@cache_control(private=True, max_age=3600)
def base(request):
    LIMIT = 10  # Initial load: 10 items for fast loading, more via lazy load
    
    # Initialize free trial for anonymous users
    if not request.user.is_authenticated:
        if 'trial_start_time' not in request.session:
            request.session['trial_start_time'] = time.time()
    
    movies = [fetch_omdb_data(title=t) for t in keyword[:LIMIT] if fetch_omdb_data(title=t)]
    shows_list = [fetch_omdb_data(title=t) for t in shows[:LIMIT] if fetch_omdb_data(title=t)]
    anime_list = [fetch_omdb_data(title=t) for t in animes[:LIMIT] if fetch_omdb_data(title=t)]
    recent_movies = [fetch_omdb_data(title=t) for t in recent_releases[:LIMIT] if fetch_omdb_data(title=t)]

    watchlist_ids = set()
    if request.user.is_authenticated:
        watchlist_ids = set(Watchlist.objects.filter(user=request.user).values_list('imdb_id', flat=True))

    return render(request, 'base.html', {
        'movies': movies,
        'shows': shows_list,
        'Animes': anime_list,
        'recent_movies': recent_movies,
        'watchlist_ids': watchlist_ids,
    })


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


def movie_view(request):
    paginator = Paginator(top_100_movies, 28)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    movies = [fetch_omdb_data(imdb_id=i) for i in page_obj.object_list if fetch_omdb_data(imdb_id=i)]

    return render(request, 'movies.html', {'page_obj': page_obj, 'movies': movies})


def anime_view(request):
    paginator = Paginator(anime_ids, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    animes_list = [fetch_omdb_data(imdb_id=i) for i in page_obj.object_list if fetch_omdb_data(imdb_id=i)]

    return render(request, 'anime.html', {'page_obj': page_obj, 'animes': animes_list})


def shows_view(request):
    paginator = Paginator(shows, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    shows_list = [fetch_omdb_data(title=t) for t in page_obj.object_list if fetch_omdb_data(title=t)]

    return render(request, 'shows.html', {'page_obj': page_obj, 'shows': shows_list})


def about_view(request):
    return render(request, 'about.html')


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

    watchlist_ids = set()
    if request.user.is_authenticated:
        watchlist_ids = set(Watchlist.objects.filter(user=request.user).values_list('imdb_id', flat=True))

    return render(request, 'detail.html', {
        'movie': movie_data,
        'season_data': season_data,
        'episodes_json': json.dumps(season_data.get('Episodes', [])),
        'recommendations': recommendations,
        'api_key': api_key,
        'watchlist_ids': watchlist_ids
    })


def fetch_more_items(request):
    category = request.GET.get('category')
    page = int(request.GET.get('page', 1))

    # Recent releases for fetch_more_items (same list as above)
    recent_releases = [
        "Oppenheimer", "Barbie", "Dune: Part Two", "Poor Things", 
        "The Holdovers", "Killers of the Flower Moon", "Past Lives",
        "Anatomy of a Fall", "The Zone of Interest", "Ferrari",
        "The Boy and the Heron", "Saltburn", "All of Us Strangers",
        "May December", "The Iron Claw", "Maestro", "The Beekeeper",
        "Mean Girls", "Dream Scenario", "The Color Purple", "American Fiction",
        "Priscilla", "The Wonderful Story of Henry Sugar", "Society of the Snow",
        "The Teachers' Lounge", "Fallen Leaves", "Perfect Days",
        "Drive-Away Dolls", "Love Lies Bleeding", "Immaculate",
        "Civil War", "Late Night with the Devil", "Abigail",
        "The Fall Guy", "IF", "Furiosa: A Mad Max Saga",
        "Hit Man", "Bad Boys: Ride or Die", "Inside Out 2",
        "A Quiet Place: Day One", "Longlegs", "Deadpool & Wolverine",
        "Trap", "Alien: Romulus", "Blink Twice",
        "Beetlejuice Beetlejuice", "The Substance", "Speak No Evil",
        "Megalopolis", "The Wild Robot", "Smile 2"
    ]
    
    config_map = {
        'movies': (top_100_movies, 28, True),
        'anime': (anime_ids, 20, True),
        'shows': (shows, 20, False),
        'popular_movies': (keyword, 50, False),  # 50 total available
        'home_shows': (shows, 50, False),  # 50 total available
        'popular_anime': (animes, 50, False),  # 50 total available
        'recent_movies': (recent_releases, 50, False),  # 50 total available
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
        if data:
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


def check_trial_status(request):
    """
    API endpoint to check free trial status for anonymous users.
    Returns trial info including remaining time and expiry status.
    """
    # Authenticated users have unlimited access
    if request.user.is_authenticated:
        return JsonResponse({
            'trial_active': False,
            'unlimited': True,
            'authenticated': True
        })
    
    # Get or initialize trial start time
    trial_start = request.session.get('trial_start_time')
    if not trial_start:
        trial_start = time.time()
        request.session['trial_start_time'] = trial_start
    
    # Calculate elapsed and remaining time
    elapsed = time.time() - trial_start
    remaining = max(0, TRIAL_DURATION - elapsed)
    
    return JsonResponse({
        'trial_active': True,
        'unlimited': False,
        'authenticated': False,
        'remaining_seconds': int(remaining),
        'expired': remaining <= 0,
        'trial_duration': TRIAL_DURATION
    })

