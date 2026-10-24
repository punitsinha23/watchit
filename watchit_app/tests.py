from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
import json
import requests
from .models import WatchParty, PartyMessage
from .views import fetch_omdb_data

class WatchPartyApprovalTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username='host', password='password123')
        self.guest = User.objects.create_user(username='guest', password='password123')
        self.client = Client()
        self.client.login(username='guest', password='password123')

    def test_public_party_requires_approval_on_access(self):
        """Users should be redirected to waiting room and added to pending for public parties."""
        party = WatchParty.objects.create(
            room_code='PUB123',
            host=self.host,
            imdb_id='tt0123456',
            is_private=False
        )
        # Access the room
        response = self.client.get(reverse('party_room', args=[party.room_code]), follow=True)
        
        # Should land on waiting room
        self.assertContains(response, "Pending Approval")
        
        # Verify guest is now a pending participant
        party.refresh_from_db()
        self.assertIn(self.guest, party.pending_participants.all())
        self.assertNotIn(self.guest, party.participants.all())

    def test_public_party_join_via_listing_goes_to_waiting(self):
        """Joining a public party via the join page listing should lead to waiting room."""
        party = WatchParty.objects.create(
            room_code='PUB456',
            host=self.host,
            imdb_id='tt0000001',
            is_private=False
        )
        # Directly visit waiting room (simulating the link from join_party.html)
        response = self.client.get(reverse('waiting_room', args=[party.room_code]))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending Approval")
        
        party.refresh_from_db()
        self.assertIn(self.guest, party.pending_participants.all())

    def test_private_party_still_requires_approval(self):
        """Joining a private party via code should still require approval."""
        party = WatchParty.objects.create(
            room_code='PRI123',
            host=self.host,
            imdb_id='tt9999999',
            is_private=True
        )
        response = self.client.post(reverse('join_watch_party'), {'room_code': 'PRI123'})
        
        # Should redirect to waiting room
        self.assertRedirects(response, reverse('waiting_room', args=[party.room_code]))
        
        party.refresh_from_db()
        self.assertIn(self.guest, party.pending_participants.all())


class PartyAccessTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username='host', password='password123')
        self.member = User.objects.create_user(username='member', password='password123')
        self.outsider = User.objects.create_user(username='outsider', password='password123')
        self.party = WatchParty.objects.create(room_code='ABC123', host=self.host, imdb_id='tt0111161', is_private=False)
        self.party.participants.add(self.member)

    def _post_json(self, name, data):
        return self.client.post(reverse(name, args=[self.party.room_code]), data=json.dumps(data), content_type='application/json')

    def test_outsider_cannot_read_status_or_chat(self):
        self.client.login(username='outsider', password='password123')
        self.assertEqual(self.client.get(reverse('api_party_status', args=['ABC123'])).status_code, 403)
        self.assertEqual(self._post_json('api_party_chat', {'text': 'hi'}).status_code, 403)
        self.assertFalse(PartyMessage.objects.exists())

    def test_member_can_chat_and_read_status(self):
        self.client.login(username='member', password='password123')
        self.assertEqual(self._post_json('api_party_chat', {'text': 'hi'}).status_code, 200)
        response = self.client.get(reverse('api_party_status', args=['ABC123']))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['messages'][0]['text'], 'hi')

    def test_delete_party_requires_post(self):
        self.client.login(username='host', password='password123')
        self.assertEqual(self.client.get(reverse('delete_party', args=['ABC123'])).status_code, 405)
        self.assertTrue(WatchParty.objects.filter(room_code='ABC123').exists())

    def test_update_rejects_invalid_input(self):
        self.client.login(username='host', password='password123')
        self.assertEqual(self._post_json('api_party_update', {'season': 'x'}).status_code, 400)
        self.assertEqual(self._post_json('api_party_update', {'source': 'evil.example'}).status_code, 400)
        self.assertEqual(self._post_json('api_party_update', {'season': 2, 'episode': 3, 'source': 'vidsrc'}).status_code, 200)

    def test_host_can_only_approve_pending_users(self):
        self.client.login(username='host', password='password123')
        response = self._post_json('api_handle_join_request', {'user_id': self.outsider.id, 'action': 'approve'})
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(self.outsider, self.party.participants.all())

    def test_expired_party_is_removed(self):
        WatchParty.objects.filter(pk=self.party.pk).update(created_at=timezone.now() - timedelta(hours=25))
        self.client.login(username='member', password='password123')
        self.assertEqual(self.client.get(reverse('api_party_status', args=['ABC123'])).status_code, 404)
        self.assertFalse(WatchParty.objects.filter(pk=self.party.pk).exists())


class FetchOmdbDataTests(TestCase):
    @patch('watchit_app.views.requests.get', side_effect=requests.ConnectionError)
    def test_returns_none_instead_of_mock_data_when_api_is_down(self, _get):
        cache.clear()
        self.assertIsNone(fetch_omdb_data(imdb_id='tt0000404'))

    @patch('watchit_app.views.requests.get', side_effect=requests.ConnectionError)
    def test_falls_back_to_exact_party_title_only(self, _get):
        cache.clear()
        host = User.objects.create_user(username='h', password='x')
        WatchParty.objects.create(room_code='UP0001', host=host, imdb_id='tt1049413', movie_title='Up in the Air')
        self.assertIsNone(fetch_omdb_data(title='Up'))
        self.assertEqual(fetch_omdb_data(imdb_id='tt1049413')['Title'], 'Up in the Air')

    @patch('watchit_app.views.requests.get')
    def test_title_is_sent_as_encoded_param(self, get):
        cache.clear()
        get.return_value.status_code = 200
        get.return_value.json.return_value = {'Response': 'True', 'Title': 'Deadpool & Wolverine'}
        fetch_omdb_data(title='Deadpool & Wolverine')
        self.assertEqual(get.call_args.kwargs['params']['t'], 'Deadpool & Wolverine')


class PageRenderTests(TestCase):
    SERIES = {'Response': 'True', 'Title': 'Show', 'Type': 'series', 'totalSeasons': '2', 'imdbID': 'tt0903747',
              'Episodes': [{'Title': '<b>Pilot</b>', 'Episode': '1'}]}

    @patch('watchit_app.views._fetch_omdb_api', return_value=None)
    @patch('watchit_app.views.fetch_tmdb_id_from_imdb', return_value=None)
    @patch('watchit_app.views.fetch_omdb_data')
    def test_pages_render_without_exposing_omdb_key(self, fetch, _tmdb, _api):
        fetch.return_value = dict(self.SERIES)
        host = User.objects.create_user(username='host', password='password123')
        WatchParty.objects.create(room_code='SER001', host=host, imdb_id='tt0903747', movie_type='series')
        self.client.login(username='host', password='password123')

        for url in [reverse('party_room', args=['SER001']), reverse('detail', args=['tt0903747'])]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertNotContains(response, 'apikey')
            self.assertNotContains(response, '<b>Pilot</b>')  # episode data is escaped

    @patch('watchit_app.views.fetch_omdb_data', return_value={'Episodes': [{'Episode': '1'}]})
    def test_episode_proxy_validates_input(self, _fetch):
        self.assertEqual(self.client.get('/api/episodes/tt0903747/1/').json(), {'Episodes': [{'Episode': '1'}]})
        self.assertEqual(self.client.get('/api/episodes/notanid/1/').status_code, 400)


class PerformanceHelperTests(TestCase):
    def setUp(self):
        cache.clear()

    @patch('watchit_app.views._fetch_omdb_api', side_effect=lambda **kw: {'Title': kw.get('title') or kw.get('imdb_id')})
    def test_fetch_omdb_many_keeps_order_and_uses_cache(self, fetch):
        from .views import fetch_omdb_many, _omdb_cache_key
        cache.set(_omdb_cache_key(title='Cached'), {'Title': 'from cache'})
        results = fetch_omdb_many([{'title': 'A'}, {'title': 'Cached'}, {'imdb_id': 'tt1'}])
        self.assertEqual([r['Title'] for r in results], ['A', 'from cache', 'tt1'])
        self.assertEqual(fetch.call_count, 2)  # cached entry skipped the API
        # fetched results were written back to the cache in one batch
        self.assertEqual(cache.get(_omdb_cache_key(title='A')), {'Title': 'A'})
        self.assertEqual(cache.get(_omdb_cache_key(imdb_id='tt1')), {'Title': 'tt1'})

    @patch('watchit_app.views._omdb_search', return_value=[])
    def test_fuzzy_search_is_capped(self, search):
        from .views import _fuzzy_omdb_search
        _fuzzy_omdb_search('a very long misspelled movie titel')
        self.assertLessEqual(search.call_count, 4)  # exact search + at most 3 prefixes


class SharedLayoutRenderTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='viewer', password='password123')

    @patch('watchit_app.views._fetch_omdb_api', return_value=None)
    def test_home_page_renders_with_static_assets(self, _fetch):
        response = self.client.get(reverse('base'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js/base.js')
        self.assertContains(response, 'css/base.css')
        self.assertContains(response, '"trialEnabled": true')

    def test_profile_page_uses_shared_layout(self):
        self.client.login(username='viewer', password='password123')
        response = self.client.get(reverse('user'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'base.html')
        self.assertContains(response, 'font-awesome/6.5.2')
        self.assertContains(response, 'id="privacyModal"', count=1)

    @patch('account_app.views.requests.get')
    def test_search_page_has_single_privacy_modal(self, get):
        get.return_value.status_code = 200
        get.return_value.json.return_value = {'Response': 'True', 'Search': [
            {'imdbID': 'tt1', 'Title': 'Found', 'Year': '2020', 'Poster': 'N/A'}]}
        self.client.login(username='viewer', password='password123')
        response = self.client.post(reverse('user_dashboard'), {'title': 'Found'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="privacyModal"', count=1)


class UiFixTests(TestCase):
    MOVIE = {'Response': 'True', 'Title': 'Some Film', 'Type': 'movie', 'imdbID': 'tt0137523',
             'Year': '1999', 'Director': 'N/A', 'Actors': 'Somebody', 'Plot': 'A plot.'}

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='viewer', email='v@example.com', password='password123')
        self.client.login(username='viewer', password='password123')

    def test_invite_link_prefills_join_form(self):
        response = self.client.get(reverse('join_watch_party') + '?code=ab12cd')
        self.assertContains(response, 'value="AB12CD"')

    @patch('watchit_app.views._fetch_omdb_api', return_value=None)
    @patch('watchit_app.views.fetch_tmdb_id_from_imdb', return_value=None)
    @patch('watchit_app.views.fetch_omdb_data')
    def test_detail_has_primary_actions_and_hides_na(self, fetch, _tmdb, _api):
        fetch.return_value = dict(self.MOVIE)
        response = self.client.get(reverse('detail', args=['tt0137523']))
        self.assertContains(response, 'Start Watch Party')
        self.assertContains(response, 'name="imdb_id" value="tt0137523"')
        self.assertNotContains(response, 'Director:')
        self.assertContains(response, 'Cast:')

    @patch('watchit_app.views.fetch_omdb_data', return_value=None)
    def test_party_room_is_responsive_and_has_invite_button(self, _fetch):
        WatchParty.objects.create(room_code='UI0001', host=self.user, imdb_id='tt0137523', movie_title='Some Film')
        response = self.client.get(reverse('party_room', args=['UI0001']))
        self.assertContains(response, 'id="chat-section" class="col-12 col-lg-3')
        self.assertContains(response, 'data-room-code="UI0001"')


class FeaturedHeroTests(TestCase):
    def setUp(self):
        cache.clear()

    @staticmethod
    def fake_api(imdb_id=None, title=None, season=None):
        names = {'tt0903747': 'Breaking Bad', 'tt4574334': 'Stranger Things', 'tt3032476': 'Better Call Saul'}
        if imdb_id in names:
            return {'Response': 'True', 'Title': names[imdb_id], 'imdbID': imdb_id, 'Type': 'series',
                    'Year': '2016–2025', 'imdbRating': '8.6', 'Genre': 'Drama, Fantasy, Horror, Mystery',
                    'Plot': 'A plot.', 'Poster': 'https://example.com/p.jpg', 'totalSeasons': '5', 'Rated': 'N/A'}
        return None

    def test_slides_link_to_the_title_they_show(self):
        with patch('watchit_app.views._fetch_omdb_api', side_effect=self.fake_api):
            response = self.client.get(reverse('base'))
        slides = response.context['featured']
        self.assertEqual([s['title'] for s in slides], ['Breaking Bad', 'Stranger Things', 'Better Call Saul'])
        self.assertContains(response, reverse('detail', args=['tt4574334']))
        self.assertNotContains(response, reverse('detail', args=['tt0944947']))  # old wrong link (Game of Thrones)
        self.assertEqual(slides[1]['genres'], ['Drama', 'Fantasy', 'Horror'])
        self.assertEqual(slides[1]['rated'], '')  # N/A is dropped
        self.assertContains(response, 'role="tab"', count=4)  # 3 titles + watch party promo

    @patch('watchit_app.views._fetch_omdb_api', return_value=None)
    def test_hero_still_renders_when_omdb_is_down(self, _api):
        response = self.client.get(reverse('base'))
        self.assertEqual(response.context['featured'], [])
        self.assertContains(response, 'Global Watch Parties')
        self.assertContains(response, 'fh-slide fh-slide-promo is-active')


class CardAndRowTests(TestCase):
    def setUp(self):
        cache.clear()

    @staticmethod
    def fake_api(imdb_id=None, title=None, season=None):
        return {'Response': 'True', 'Title': title or imdb_id, 'imdbID': f'tt{abs(hash(title or imdb_id)) % 10**7:07d}',
                'Type': 'movie', 'Year': '2020', 'imdbRating': '7.9', 'Poster': 'N/A'}

    def test_home_rows_use_shared_card(self):
        with patch('watchit_app.views._fetch_omdb_api', side_effect=self.fake_api):
            response = self.client.get(reverse('base'))
        self.assertContains(response, 'class="mcard"')
        self.assertContains(response, '<i class="fas fa-star"></i>7.9')
        self.assertContains(response, 'img/poster-placeholder.svg')  # N/A poster -> local placeholder
        self.assertNotContains(response, 'src="N/A"')
        self.assertEqual([r['title'] for r in response.context['home_rows']],
                         ['Recently Released', 'Popular Movies', 'Popular Shows', 'Popular Anime'])

    def test_my_list_row_for_logged_in_users(self):
        from account_app.models import Watchlist
        user = User.objects.create_user(username='u', password='password123')
        Watchlist.objects.create(user=user, imdb_id='tt0111161', movie_title='Saved Film', movie_year='1994')
        self.client.login(username='u', password='password123')
        with patch('watchit_app.views._fetch_omdb_api', return_value=None):
            response = self.client.get(reverse('base'))
        rows = response.context['home_rows']
        self.assertEqual(rows[0]['title'], 'My List')
        self.assertContains(response, 'Saved Film')
        self.assertContains(response, 'title="Remove from My List"')

    def test_fetch_more_includes_rating_and_type(self):
        with patch('watchit_app.views._fetch_omdb_api', side_effect=self.fake_api):
            data = self.client.get('/fetch-more/?category=popular_movies&page=2').json()
        self.assertEqual(data['items'][0]['imdbRating'], '7.9')
        self.assertEqual(data['items'][0]['Type'], 'movie')


class CacheOutageTests(TestCase):
    """Production 500: the cache table was missing because `migrate` hadn't run."""

    def test_pages_work_when_cache_table_is_missing(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE watchit_cache')  # rolled back after the test
        with patch('watchit_app.views._fetch_omdb_api', return_value=None), self.assertLogs('watchit.cache', 'ERROR'):
            self.assertEqual(self.client.get(reverse('base')).status_code, 200)
            self.assertEqual(self.client.get('/fetch-more/?category=popular_movies&page=2').status_code, 200)
            self.assertEqual(self.client.get('/api/episodes/tt0903747/1/').status_code, 200)
