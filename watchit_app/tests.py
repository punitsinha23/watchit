from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import WatchParty

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
