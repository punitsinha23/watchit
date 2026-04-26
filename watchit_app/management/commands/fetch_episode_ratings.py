import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.core.management.base import BaseCommand
from django.conf import settings
from watchit_app.models import EpisodeRating, ShowMapping


class Command(BaseCommand):
    help = 'Fetches episode ratings for a TV show from TMDB'

    def add_arguments(self, parser):
        parser.add_argument('show_id', type=str, help='TMDB Show ID')
        parser.add_argument('--imdb', type=str, help='IMDB ID to link (e.g. tt0903747)', default=None)

    def _get_session(self):
        """Create a requests session with retry logic."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        return session

    def handle(self, *args, **options):
        show_id = options['show_id']
        api_key = settings.TMDB_API_KEY
        base_url = "https://api.themoviedb.org/3"

        if not api_key:
            self.stdout.write(self.style.ERROR('TMDB_API_KEY not found in settings. Add it to your .env file.'))
            return

        session = self._get_session()

        # 1. Get show details to find out the number of seasons
        show_url = f"{base_url}/tv/{show_id}?api_key={api_key}"
        try:
            response = session.get(show_url, timeout=15)
        except requests.exceptions.ConnectionError as e:
            self.stdout.write(self.style.ERROR(
                f'Network error connecting to TMDB API. This is usually caused by a VPN, '
                f'firewall, or antivirus blocking the connection.\n'
                f'Try: 1) Disable VPN  2) Check firewall  3) Try again later\n'
                f'Error: {e}'
            ))
            return

        if response.status_code != 200:
            self.stdout.write(self.style.ERROR(f'Error fetching show details: {response.status_code} - {response.text}'))
            return

        show_data = response.json()
        show_name = show_data.get('name', 'Unknown')
        seasons = show_data.get('seasons', [])
        self.stdout.write(f"Found show: {show_name} with {len(seasons)} seasons")

        # Save IMDB→TMDB mapping if --imdb was provided
        imdb_id = options.get('imdb')
        if imdb_id:
            ShowMapping.objects.update_or_create(
                imdb_id=imdb_id,
                defaults={'tmdb_id': show_id, 'show_name': show_name}
            )
            self.stdout.write(f"Saved mapping: {imdb_id} -> {show_id}")

        total_saved = 0
        for season in seasons:
            season_num = season.get('season_number')
            if season_num == 0:
                continue

            self.stdout.write(f"Fetching Season {season_num}...")
            season_url = f"{base_url}/tv/{show_id}/season/{season_num}?api_key={api_key}"

            try:
                season_resp = session.get(season_url, timeout=15)
                time.sleep(0.3)  # Be polite to the API
            except requests.exceptions.ConnectionError:
                self.stdout.write(self.style.WARNING(f"  Network error on Season {season_num}, skipping..."))
                continue

            if season_resp.status_code != 200:
                self.stdout.write(self.style.WARNING(f"  Skipping Season {season_num} (HTTP {season_resp.status_code})"))
                continue

            episodes = season_resp.json().get('episodes', [])
            season_saved = 0
            for ep in episodes:
                vote_count = ep.get('vote_count', 0)
                if vote_count == 0:
                    continue

                EpisodeRating.objects.update_or_create(
                    show_id=show_id,
                    season_number=season_num,
                    episode_number=ep.get('episode_number'),
                    defaults={
                        'episode_name': ep.get('name', ''),
                        'rating': ep.get('vote_average', 0.0),
                        'vote_count': vote_count,
                        'air_date': ep.get('air_date') if ep.get('air_date') else None,
                    }
                )
                season_saved += 1

            total_saved += season_saved
            self.stdout.write(f"  Saved {season_saved} episodes for Season {season_num}")

        self.stdout.write(self.style.SUCCESS(f'Done! Saved {total_saved} episode ratings for "{show_name}" (ID: {show_id})'))
