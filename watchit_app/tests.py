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

    @patch('watchit_app.views.fetch_tmdb_id_from_imdb', return_value=None)
    @patch('watchit_app.views.fetch_omdb_data')
    def test_pages_render_without_exposing_omdb_key(self, fetch, _tmdb):
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
