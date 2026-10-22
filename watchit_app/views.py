from django.shortcuts import render, redirect
from django.contrib import messages
from account_app.models import Watchlist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
import json
import logging
import random
import re
import requests
import time
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db.models import Max
from django.views.decorators.http import require_POST
from decouple import config
from .models import WatchParty, PartyMessage, EpisodeRating, ShowMapping
from .data import keyword, shows, top_100_movies, animes, anime_ids
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)

api_key = config('OMDB_KEY', default='')
api_key_2 = config('OMDB_KEY_2', default='')

OMDB_URL = "https://www.omdbapi.com/"
PARTY_TTL_SECONDS = 24 * 60 * 60
ALLOWED_SOURCES = {'embedmaster', 'vidsrc', 'vidsrcto', 'vidsrcme', 'superembed'}
MAX_CHAT_LENGTH = 1000
OMDB_WORKERS = 8
IMDB_ID_RE = re.compile(r'^tt\d{5,10}$')


def _get_live_party(room_code, **filters):
    """Return the active party for room_code, deleting it if it is older than 24 hours."""
    party = WatchParty.objects.filter(room_code=room_code, is_active=True, **filters).first()
    if party and (timezone.now() - party.created_at).total_seconds() > PARTY_TTL_SECONDS:
        party.delete()
        return None
    return party


def _is_member(party, user):
    """Host or approved participant."""
    return user == party.host or party.participants.filter(id=user.id).exists()


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

    movie_data = fetch_omdb_data(imdb_id=imdb_id)
    if not movie_data:
        return redirect('base')

    movie_title = movie_data.get('Title', '')
    poster_url = movie_data.get('Poster', '')

    party = WatchParty.objects.create(
        room_code=room_code,
        host=request.user,
        imdb_id=imdb_id,
        movie_title=movie_title,
        movie_type=movie_data.get('Type', 'movie'),
        poster_url=poster_url,
        total_seasons=int(movie_data.get('totalSeasons', 0)) if str(movie_data.get('totalSeasons', '0')).isdigit() else 0,
        current_season=1,
        current_episode=1,
        is_private=is_private
    )
    return redirect('party_room', room_code=room_code)

@login_required
def join_watch_party(request):
    public_parties = WatchParty.objects.filter(is_active=True, is_private=False).exclude(host=request.user).order_by('-created_at')

    if request.method == 'POST':
        room_code = request.POST.get('room_code', '').strip().upper()
        party = _get_live_party(room_code)
        if not party:
            return render(request, 'join_party.html', {
                'error': 'Invalid or expired room code',
                'public_parties': public_parties
            })

        # If already a participant or the host, go straight in
        if _is_member(party, request.user):
            return redirect('party_room', room_code=room_code)

        party.pending_participants.add(request.user)
        return redirect('waiting_room', room_code=room_code)
    # Invite links point here as /party/join/?code=XXXXXX
    prefill_code = request.GET.get('code', '').strip().upper()[:6]
    return render(request, 'join_party.html', {'public_parties': public_parties, 'prefill_code': prefill_code})

@login_required
def waiting_room(request, room_code):
    party = _get_live_party(room_code)
    if not party:
        return redirect('base')

    if _is_member(party, request.user):
        return redirect('party_room', room_code=room_code)

    party.pending_participants.add(request.user)
    return render(request, 'waiting_room.html', {'party': party})

@login_required
def api_check_approval(request, room_code):
    party = _get_live_party(room_code)
    if not party:
        return JsonResponse({'status': 'room_gone'})

    if party.participants.filter(id=request.user.id).exists():
        return JsonResponse({'status': 'approved'})

    if not party.pending_participants.filter(id=request.user.id).exists():
        return JsonResponse({'status': 'denied'})

    return JsonResponse({'status': 'pending'})


@login_required
def party_room(request, room_code):
    party = _get_live_party(room_code)
    if not party:
        return redirect('base')

    # Access check: Host or Participant only
    if not _is_member(party, request.user):
        return redirect('waiting_room', room_code=room_code)

    movie_data = fetch_omdb_data(imdb_id=party.imdb_id)
    if not movie_data:
        # OMDb unavailable: fall back to the metadata stored on the party
        movie_data = {
            'Title': party.movie_title or '',
            'Poster': party.poster_url or '',
            'imdbID': party.imdb_id,
            'Type': party.movie_type,
            'totalSeasons': party.total_seasons,
        }

    # Persist metadata to DB if missing
    if not party.movie_title or not party.total_seasons:
        party.movie_title = movie_data.get('Title', party.movie_title)
        party.movie_type = movie_data.get('Type', party.movie_type)
        try:
            party.total_seasons = int(movie_data.get('totalSeasons', party.total_seasons))
        except (ValueError, TypeError):
            pass
        party.save()

    # Normalize totalSeasons
    try:
        movie_data['totalSeasons'] = int(movie_data.get('totalSeasons', 0))
    except (ValueError, TypeError):
        movie_data['totalSeasons'] = 0

    season_data = {}
    if movie_data.get('Type') == 'series':
        season_data = fetch_omdb_data(imdb_id=party.imdb_id, season=party.current_season) or {}

    return render(request, 'watch_party.html', {
        'party': party,
        'movie': movie_data,
        'season_data': season_data,
        'is_host': request.user == party.host,
    })

@login_required
def api_party_status(request, room_code):
    party = _get_live_party(room_code)
    if not party:
        return JsonResponse({'error': 'Party not found'}, status=404)

    if not _is_member(party, request.user):
        return JsonResponse({'error': 'Not a participant'}, status=403)

    # Fetch messages since 'last_msg_id' if provided
    try:
        last_msg_id = int(request.GET.get('last_msg_id', 0))
    except ValueError:
        last_msg_id = 0
    new_messages = party.messages.filter(id__gt=last_msg_id).select_related('user').order_by('timestamp')

    msgs_data = [{
        'id': m.id,
        'user': m.user.username,
        'text': m.text,
        'timestamp': m.timestamp.strftime('%H:%M')
    } for m in new_messages]

    # Viewer tracking
    current_time = time.time()
    v_cache_key = f"viewers_{room_code}"
    # Structure: {user_id: last_heartbeat_timestamp}
    viewers_map = cache.get(v_cache_key, {})
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

@login_required
@require_POST
def api_handle_join_request(request, room_code):
    party = _get_live_party(room_code, host=request.user)
    if not party:
        return JsonResponse({'error': 'Party not found or unauthorized'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    user_id = data.get('user_id')
    action = data.get('action')  # 'approve' or 'deny'

    # Only users who actually asked to join can be approved
    user_to_handle = party.pending_participants.filter(id=user_id).first()
    if not user_to_handle:
        return JsonResponse({'error': 'User not found'}, status=404)

    party.pending_participants.remove(user_to_handle)
    if action == 'approve':
        party.participants.add(user_to_handle)
    return JsonResponse({'status': 'ok'})

@login_required
@require_POST
def delete_party(request, room_code):
    WatchParty.objects.filter(room_code=room_code, host=request.user).delete()
    return redirect('user')


@login_required
@require_POST
def api_party_update(request, room_code):
    party = _get_live_party(room_code)
    if not party:
        return JsonResponse({'error': 'Party not found'}, status=404)

    if request.user != party.host:
        return JsonResponse({'error': 'Only host can update settings'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    try:
        season = int(data.get('season', party.current_season))
        episode = int(data.get('episode', party.current_episode))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Season and episode must be integers'}, status=400)
    source = data.get('source', party.current_source)
    if season < 1 or episode < 1 or source not in ALLOWED_SOURCES:
        return JsonResponse({'error': 'Invalid season, episode or source'}, status=400)

    party.current_season = season
    party.current_episode = episode
    party.current_source = source
    party.save(update_fields=['current_season', 'current_episode', 'current_source'])

    return JsonResponse({'status': 'ok'})

@login_required
@require_POST
def api_party_chat(request, room_code):
    party = _get_live_party(room_code)
    if not party:
        return JsonResponse({'error': 'Party not found'}, status=404)

    if not _is_member(party, request.user):
        return JsonResponse({'error': 'Not a participant'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    text = str(data.get('text', '')).strip()[:MAX_CHAT_LENGTH]
    if text:
        PartyMessage.objects.create(party=party, user=request.user, text=text)

    return JsonResponse({'status': 'ok'})


def api_season_episodes(request, imdb_id, season):
    """Server-side proxy so the OMDb key never reaches the browser."""
    if not IMDB_ID_RE.match(imdb_id) or not 1 <= season <= 100:
        return JsonResponse({'error': 'Invalid request'}, status=400)
    data = fetch_omdb_data(imdb_id=imdb_id, season=season) or {}
    return JsonResponse({'Episodes': data.get('Episodes', [])})

# Free trial duration in seconds (45 minutes)
TRIAL_DURATION = 45 * 60  # 2700 seconds


def _trial_remaining(request):
    """Seconds left in an anonymous user's free trial, starting it if needed."""
    trial_start = request.session.get('trial_start_time')
    if not trial_start:
        trial_start = time.time()
        request.session['trial_start_time'] = trial_start
    return max(0, TRIAL_DURATION - (time.time() - trial_start))


def _omdb_cache_key(imdb_id=None, title=None, season=None):
    return f"omdb_{imdb_id or title}_{season or 'main'}".replace(" ", "_")


def fetch_omdb_many(lookups):
    """
    Run fetch_omdb_data for each kwargs dict in `lookups` and return the
    results in the same order (None for misses). Cached entries are read in a
    single query; only cache misses hit the API, concurrently. Worker threads
    only do network I/O -- all cache writes happen here in one batch, which
    avoids lost writes from concurrent DB-cache inserts.
    """
    keys = [_omdb_cache_key(**kw) for kw in lookups]
    cached = cache.get_many(keys)
    results = [cached.get(k) for k in keys]
    missing = [i for i, r in enumerate(results) if r is None]
    if not missing:
        return results

    with ThreadPoolExecutor(max_workers=min(OMDB_WORKERS, len(missing))) as pool:
        fetched = list(pool.map(lambda kw: _fetch_omdb_api(**kw), [lookups[i] for i in missing]))

    to_cache = {}
    for i, data in zip(missing, fetched):
        if data:
            results[i] = data
            to_cache[keys[i]] = data
        else:
            results[i] = _party_fallback(**lookups[i])
    if to_cache:
        cache.set_many(to_cache, 86400)  # 24 hours
    return results


def fetch_omdb_data(imdb_id=None, title=None, season=None):
    """
    Fetch data from the OMDb API, with caching and a fallback to metadata
    stored on existing watch parties. Returns None when nothing is found.
    """
    if not imdb_id and not title:
        return None

    cache_key = _omdb_cache_key(imdb_id, title, season)
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    data = _fetch_omdb_api(imdb_id, title, season)
    if data:
        cache.set(cache_key, data, 86400)  # 24 hours
        return data
    return _party_fallback(imdb_id, title, season)


def _fetch_omdb_api(imdb_id=None, title=None, season=None):
    """
    Query OMDb, failing over between the two API keys. Network only: no
    cache writes or DB access, so it is safe to run in worker threads.
    """
    if not imdb_id and not title:
        return None

    params = {'i': imdb_id, 'plot': 'full'} if imdb_id else {'t': title}
    if imdb_id and season:
        params['Season'] = season

    for current_key in [api_key, api_key_2]:
        if not current_key or current_key in _bad_omdb_keys():
            continue

        try:
            response = requests.get(OMDB_URL, params={**params, 'apikey': current_key}, timeout=5)
        except requests.RequestException as e:
            logger.warning("OMDb request failed for key %s...: %s", current_key[:4], e)
            continue

        if response.status_code == 401:
            _mark_omdb_key_bad(current_key)
            continue
        if response.status_code != 200:
            continue

        data = response.json()
        if data.get("Response") == "True":
            return data

        error_msg = data.get("Error", "").lower()
        if "limit" in error_msg or "key" in error_msg:
            _mark_omdb_key_bad(current_key)
            continue
        break  # Not found etc. -- another key won't help
    return None


# Keys that recently hit their limit or were rejected are skipped for 10 minutes.
# Kept in process memory so worker threads never write to the DB cache.
_omdb_bad_keys = {}


def _bad_omdb_keys():
    now = time.time()
    return {k for k, until in list(_omdb_bad_keys.items()) if until > now}


def _mark_omdb_key_bad(key):
    _omdb_bad_keys[key] = time.time() + 600


def _party_fallback(imdb_id=None, title=None, season=None):
    """Metadata stored on an existing party, for when OMDb is unavailable (main lookups only)."""
    if season:
        return None
    parties = WatchParty.objects.exclude(movie_title="").exclude(movie_title__isnull=True)
    party = parties.filter(imdb_id=imdb_id).first() if imdb_id else parties.filter(movie_title__iexact=title).first()
    if not party:
        return None
    return {
        "Title": party.movie_title,
        "Poster": party.poster_url,
        "imdbID": party.imdb_id,
        "Type": party.movie_type,
        "totalSeasons": str(party.total_seasons),
        "Response": "True",
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

# Hero slides on the home page. Titles, ratings and plots come from OMDb by ID,
# so the text always matches the title the buttons open.
FEATURED = [
    {'imdb_id': 'tt0903747',  # Breaking Bad
     'backdrop': 'https://www.sonypictures.com/sites/default/files/banner-images/2023-12/breakingbad_banner_2572x1100.jpg'},
    {'imdb_id': 'tt4574334',  # Stranger Things
     'backdrop': 'https://mir-s3-cdn-cf.behance.net/project_modules/fs/415b2e58808319.5bf89df796f80.jpg'},
    {'imdb_id': 'tt3032476',  # Better Call Saul
     'backdrop': 'https://www.sonypictures.com/sites/default/files/banner-images/2022-03/bettercallsaul_banner_2572x1100_s6.jpg'},
]


def _featured_slides(results):
    """Merge OMDb data into FEATURED; slides whose lookup failed are skipped."""
    slides = []
    for item, data in zip(FEATURED, results):
        if not data:
            continue
        has = lambda key: data.get(key) not in (None, '', 'N/A')
        genres = data.get('Genre', '').split(', ')[:3] if has('Genre') else []
        slides.append({
            'imdb_id': item['imdb_id'],
            'backdrop': item['backdrop'],
            'title': data.get('Title'),
            'type': 'Series' if data.get('Type') == 'series' else 'Movie',
            'year': data.get('Year') if has('Year') else '',
            'seasons': data.get('totalSeasons') if has('totalSeasons') else '',
            'rating': data.get('imdbRating') if has('imdbRating') else '',
            'rated': data.get('Rated') if has('Rated') else '',
            'genres': genres,
            'plot': data.get('Plot') if has('Plot') else '',
            'poster': data.get('Poster') if has('Poster') else '',
        })
    return slides


def base(request):
    LIMIT = 10  # Initial load: 10 items for fast loading, more via lazy load
    
    # Initialize free trial for anonymous users
    if not request.user.is_authenticated:
        if 'trial_start_time' not in request.session:
            request.session['trial_start_time'] = time.time()
    
    rows = [keyword[:LIMIT], shows[:LIMIT], animes[:LIMIT], recent_releases[:LIMIT]]
    # One batch for the hero slides and all four rows
    results = fetch_omdb_many(
        [{'imdb_id': f['imdb_id']} for f in FEATURED] + [{'title': t} for row in rows for t in row]
    )
    featured, results = _featured_slides(results[:len(FEATURED)]), results[len(FEATURED):]
    movies, shows_list, anime_list, recent_movies = (
        [data for data in results[i * LIMIT:(i + 1) * LIMIT] if data] for i in range(len(rows))
    )

    watchlist_ids = set()
    home_rows = []
    if request.user.is_authenticated:
        saved = list(Watchlist.objects.filter(user=request.user))
        watchlist_ids = {w.imdb_id for w in saved}
        if saved:
            home_rows.append({
                'title': 'My List', 'subtitle': 'Saved for later', 'icon': 'fa-bookmark', 'accent': 'green',
                'items': [{'imdbID': w.imdb_id, 'Title': w.movie_title, 'Year': w.movie_year, 'Poster': w.poster}
                          for w in saved[:20]],
            })

    home_rows += [
        {'title': 'Recently Released', 'subtitle': 'The newest additions to the platform', 'icon': 'fa-fire',
         'accent': 'red', 'badge': 'New', 'category': 'recent_movies', 'items': recent_movies},
        {'title': 'Popular Movies', 'subtitle': 'What everyone is watching right now', 'icon': 'fa-film',
         'accent': 'blue', 'badge': 'Trending', 'category': 'popular_movies', 'items': movies},
        {'title': 'Popular Shows', 'subtitle': 'Binge-worthy series to start today', 'icon': 'fa-tv',
         'accent': 'yellow', 'category': 'home_shows', 'items': shows_list},
        {'title': 'Popular Anime', 'subtitle': 'Top-rated anime series and movies', 'icon': 'fa-dragon',
         'accent': 'pink', 'category': 'popular_anime', 'items': anime_list},
    ]

    return render(request, 'base.html', {
        'featured': featured,
        'home_rows': [row for row in home_rows if row['items']],
        'watchlist_ids': watchlist_ids,
    })


def _omdb_search(query, max_pages=3):
    """
    Fetch up to max_pages * 10 results from OMDB for a given query.
    Returns a list of movie dicts or an empty list.
    """
    results = []
    for page in range(1, max_pages + 1):
        try:
            resp = requests.get(OMDB_URL, params={'apikey': api_key, 's': query, 'page': page}, timeout=5)
            if resp.status_code != 200:
                break
            data = resp.json()
            if data.get("Response") != "True":
                break
            batch = data.get("Search", [])
            results.extend(batch)
            # If this page has fewer than 10 results, there are no more pages
            if len(batch) < 10:
                break
        except Exception:
            break
    return results


def _fuzzy_omdb_search(query, max_pages=3):
    """
    Try an exact OMDB search first. If no results, progressively shorten the
    query (removing the last character each time, down to 4 chars) to provide
    typo-tolerant 'did you mean'-style results.
    """
    # Exact search first
    results = _omdb_search(query, max_pages)
    if results:
        return results, None

    # Fallback: a few progressively shorter prefixes, searched concurrently
    MIN_LEN, MAX_ATTEMPTS = 4, 3
    candidates = []
    words = query.split()
    for prefix in [
        ' '.join(words[:-1]) if len(words) > 1 else '',  # drop the last word
        query[:-1],
        query[:-2],
        query[:max(MIN_LEN, int(len(query) * 0.75))],
    ]:
        prefix = prefix.strip()
        if len(prefix) >= MIN_LEN and prefix != query and prefix not in candidates:
            candidates.append(prefix)
    candidates = candidates[:MAX_ATTEMPTS]
    if not candidates:
        return [], None

    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        attempts = list(pool.map(lambda q: _omdb_search(q, max_pages=1), candidates))
    for prefix, results in zip(candidates, attempts):
        if results:
            return results, prefix  # return prefix so UI can hint "Showing results for: ..."

    return [], None


def dashboard(request):
    movie_data = None
    error = None
    fuzzy_suggestion = None

    if request.method == "POST":
        movie_title = request.POST.get('title', '').strip()

        if not movie_title:
            error = "Please enter a movie title."
            return render(request, 'dashboard.html', {'movie_data': movie_data, 'error': error})

        cache_key = f"search_{movie_title.lower()}".replace(" ", "_")
        cached = cache.get(cache_key)

        if cached:
            movie_data = cached.get('results')
            fuzzy_suggestion = cached.get('suggestion')
        else:
            try:
                movie_data, fuzzy_suggestion = _fuzzy_omdb_search(movie_title)
                if movie_data:
                    cache.set(cache_key, {'results': movie_data, 'suggestion': fuzzy_suggestion}, 3600)
                else:
                    error = f"No results found for \"{movie_title}\". Try a different spelling."
            except Exception as e:
                error = f"An error occurred: {str(e)}"

    watchlist_ids = set()
    if request.user.is_authenticated:
        watchlist_ids = set(Watchlist.objects.filter(user=request.user).values_list('imdb_id', flat=True))

    return render(request, 'dashboard.html', {
        'movie_data': movie_data,
        'error': error,
        'watchlist_ids': watchlist_ids,
        'fuzzy_suggestion': fuzzy_suggestion,
    })


def movie_view(request):
    paginator = Paginator(top_100_movies, 28)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    movies = [data for i in page_obj.object_list if (data := fetch_omdb_data(imdb_id=i))]

    return render(request, 'movies.html', {'page_obj': page_obj, 'movies': movies})


def anime_view(request):
    paginator = Paginator(anime_ids, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    animes_list = [data for i in page_obj.object_list if (data := fetch_omdb_data(imdb_id=i))]

    return render(request, 'anime.html', {'page_obj': page_obj, 'animes': animes_list})


def shows_view(request):
    paginator = Paginator(shows, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    shows_list = [data for t in page_obj.object_list if (data := fetch_omdb_data(title=t))]

    return render(request, 'shows.html', {'page_obj': page_obj, 'shows': shows_list})


def about_view(request):
    return render(request, 'about.html')


def detail_view(request, imdb_id):
    if not request.user.is_authenticated and _trial_remaining(request) <= 0:
        messages.info(request, "Your free trial has ended. Log in to keep watching.")
        return redirect('login')

    movie_data = fetch_omdb_data(imdb_id=imdb_id)
    if not movie_data:
        return redirect('base')

    # Normalize totalSeasons and save back to first party if possible
    try:
        total_seasons = int(movie_data.get('totalSeasons', 0))
        movie_data['totalSeasons'] = total_seasons
        # Try to update an existing watch party with this data so it's persisted in DB
        # for future fetch_omdb_data calls
        party_to_update = WatchParty.objects.filter(imdb_id=imdb_id).first()
        if party_to_update:
            if not party_to_update.movie_title:
                party_to_update.movie_title = movie_data.get('Title')
            party_to_update.movie_type = movie_data.get('Type', 'movie')
            party_to_update.total_seasons = total_seasons
            party_to_update.save()
    except (ValueError, TypeError):
        movie_data['totalSeasons'] = 0

    season_data = {}
    if movie_data.get('Type') == 'series':
        season_data = fetch_omdb_data(imdb_id=imdb_id, season=1) or {}

    # Recommend from the curated lists of the same kind (series vs movies)
    pool = shows + animes if movie_data.get('Type') == 'series' else keyword + recent_releases
    rec_titles = random.sample(pool, min(len(pool), 14))
    recommendations, seen = [], {imdb_id}
    for data in fetch_omdb_many([{'title': t} for t in rec_titles]):
        # different list entries can resolve to the same title (e.g. "Money Heist" / "La Casa de Papel")
        if data and data.get('Poster') not in (None, '', 'N/A') and data.get('imdbID') not in seen:
            seen.add(data.get('imdbID'))
            recommendations.append(data)
    recommendations = recommendations[:12]

    watchlist_ids = set()
    if request.user.is_authenticated:
        watchlist_ids = set(Watchlist.objects.filter(user=request.user).values_list('imdb_id', flat=True))

    tmdb_id = None
    if movie_data.get('Type') == 'series':
        tmdb_id = fetch_tmdb_id_from_imdb(imdb_id)

    return render(request, 'detail.html', {
        'movie': movie_data,
        'season_data': season_data,
        'episodes': season_data.get('Episodes', []),
        'recommendations': recommendations,
        'watchlist_ids': watchlist_ids,
        'tmdb_id': tmdb_id
    })


def fetch_tmdb_id_from_imdb(imdb_id):
    """
    Helper to get TMDB TV show ID from IMDB ID.
    First checks the local ShowMapping cache, then falls back to TMDB API.
    """
    # 1. Check local DB cache first (instant, no API call)
    from django.db.utils import ProgrammingError
    try:
        mapping = ShowMapping.objects.get(imdb_id=imdb_id)
        return mapping.tmdb_id
    except (ShowMapping.DoesNotExist, ProgrammingError):
        # Fall back to API if table is missing or entry not found
        pass

    # 2. Fall back to TMDB API
    tmdb_key = settings.TMDB_API_KEY
    if not tmdb_key:
        return None

    url = f"https://api.themoviedb.org/3/find/{imdb_id}"
    params = {'api_key': tmdb_key, 'external_source': 'imdb_id'}

    # Retry on WinError 10054 (Connection Reset)
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                tv_results = resp.json().get('tv_results', [])
                if tv_results:
                    tmdb_id = tv_results[0].get('id')
                    try:
                        ShowMapping.objects.update_or_create(
                            imdb_id=imdb_id,
                            defaults={'tmdb_id': str(tmdb_id), 'show_name': tv_results[0].get('name', '')}
                        )
                    except ProgrammingError:
                        pass
                    return tmdb_id
            elif resp.status_code == 429:
                time.sleep(1)
                continue
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            time.sleep(0.5)
            continue
    return None


def fetch_more_items(request):
    category = request.GET.get('category')
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except ValueError:
        return JsonResponse({'error': 'Invalid page'}, status=400)

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
    is_authenticated = request.user.is_authenticated
    login_url = reverse('login')

    lookups = [{'imdb_id': item} if use_id else {'title': item} for item in all_items[start:end]]
    for data in fetch_omdb_many(lookups):
        if data:
            imdb_id = data.get('imdbID')
            destination_url = reverse('detail', args=[imdb_id]) if is_authenticated else login_url

            items.append({
                'imdbID': imdb_id,
                'Title': data.get('Title'),
                'Poster': data.get('Poster'),
                'Year': data.get('Year'),
                'Type': data.get('Type'),
                'imdbRating': data.get('imdbRating'),
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
    
    remaining = _trial_remaining(request)
    
    return JsonResponse({
        'trial_active': True,
        'unlimited': False,
        'authenticated': False,
        'remaining_seconds': int(remaining),
        'expired': remaining <= 0,
        'trial_duration': TRIAL_DURATION
    })


def show_episode_chart(request, show_id):
    """
    Groups ratings by season for the UI.
    Resolves IMDB ID to TMDB ID if needed.
    """
    # 1. Resolve ID if it looks like an IMDB ID (starts with tt)
    tmdb_id = show_id
    if str(show_id).startswith('tt'):
        tmdb_id = fetch_tmdb_id_from_imdb(show_id)
        if not tmdb_id:
            return JsonResponse({'error': 'ID resolution failed', 'data': []})

    # 2. Check for data and repair if missing
    from django.db.utils import ProgrammingError
    try:
        last_fetch = EpisodeRating.objects.filter(show_id=tmdb_id).aggregate(Max('fetched_at'))['fetched_at__max']
        if not last_fetch or timezone.now() - last_fetch > timedelta(days=1):
            _auto_fetch_ratings(tmdb_id)
        ratings = EpisodeRating.objects.filter(show_id=tmdb_id).order_by('season_number', 'episode_number')
    except (EpisodeRating.DoesNotExist, ProgrammingError):
        return JsonResponse({'error': 'Ratings database not initialized', 'data': []})
    
    data = []
    for r in ratings:
        data.append({
            'season': r.season_number,
            'episode': r.episode_number,
            'label': f"S{r.season_number}E{r.episode_number}",
            'name': r.episode_name,
            'rating': float(r.rating)
        })
        
    return JsonResponse({'data': data})


def _auto_fetch_ratings(show_id):
    """
    Background helper for TMDB data synchronization.
    """
    api_key = settings.TMDB_API_KEY
    if not api_key:
        return
    
    base_url = "https://api.themoviedb.org/3"
    
    try:
        # 1. Get show structure
        response = requests.get(f"{base_url}/tv/{show_id}?api_key={api_key}", timeout=10)
        if response.status_code != 200:
            return
        
        show_data = response.json()
        seasons = show_data.get('seasons', [])
        
        # 2. Fetch missing seasons, and always refresh the latest one (it may still be airing)
        existing_seasons = set(EpisodeRating.objects.filter(show_id=show_id).values_list('season_number', flat=True))
        latest_season = max((s.get('season_number') or 0 for s in seasons), default=0)
        
        for season in seasons:
            s_num = season.get('season_number')
            if s_num == 0 or (s_num in existing_seasons and s_num != latest_season):
                continue
            
            # Retry loop for network connection resets (10054)
            for attempt in range(3):
                try:
                    time.sleep(0.35) # Rate limit protection
                    s_resp = requests.get(
                        f"{base_url}/tv/{show_id}/season/{s_num}?api_key={api_key}",
                        timeout=20
                    )
                    if s_resp.status_code == 200:
                        for ep in s_resp.json().get('episodes', []):
                            if ep.get('vote_count', 0) > 0:
                                try:
                                    EpisodeRating.objects.update_or_create(
                                        show_id=show_id, season_number=s_num,
                                        episode_number=ep.get('episode_number'),
                                        defaults={
                                            'episode_name': ep.get('name', ''),
                                            'rating': ep.get('vote_average', 0.0),
                                            'vote_count': ep.get('vote_count'),
                                            'air_date': ep.get('air_date') or None
                                        }
                                    )
                                except ProgrammingError:
                                    pass
                        break
                    elif s_resp.status_code == 429:
                        time.sleep(2)
                        continue
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                    time.sleep(1)
                    continue
    except Exception:
        logger.exception("Episode rating fetch failed for %s", show_id)
