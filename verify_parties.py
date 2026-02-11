import os
import django
from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User
from watchit_app.models import WatchParty

# Setup Django
import sys
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'watchit.settings')
django.setup()

def run_tests():
    print("Starting Watch Party Auto-Join Tests...")
    
    # 1. Setup users
    host_user, _ = User.objects.get_or_create(username='test_host', email='host@test.com')
    host_user.set_password('pass123')
    host_user.save()
    
    guest_user, _ = User.objects.get_or_create(username='test_guest', email='guest@test.com')
    guest_user.set_password('pass123')
    guest_user.save()
    
    client = Client()
    client.login(username='test_guest', password='pass123')
    
    # 2. Test Public Party Join (Direct Link)
    public_party = WatchParty.objects.create(
        room_code='PUB123',
        host=host_user,
        imdb_id='tt0123456',
        is_private=False
    )
    
    print(f"Testing direct access to PUBLIC room {public_party.room_code}...")
    response = client.get(reverse('party_room', args=[public_party.room_code]))
    
    # Refresh from DB
    public_party.refresh_from_db()
    if guest_user in public_party.participants.all():
        print("PASS: Guest auto-joined public room.")
    else:
        print("FAIL: Guest failed to auto-join public room.")
        
    # 3. Test Private Party Join (Should go to waiting room)
    private_party = WatchParty.objects.create(
        room_code='PRIV12',
        host=host_user,
        imdb_id='tt6543210',
        is_private=True
    )
    
    print(f"Testing direct access to PRIVATE room {private_party.room_code}...")
    response = client.get(reverse('party_room', args=[private_party.room_code]))
    
    if response.status_code == 302 and 'waiting_room' in response.url:
        print("PASS: Guest redirected to waiting room for private party.")
    else:
        print(f"FAIL: Unexpected response for private party access: {response.status_code} to {response.get('Location', 'N/A')}")

    # 4. Test Join Party via Code (Public)
    print(f"Testing POST join to PUBLIC room {public_party.room_code} via code...")
    # Clear participant first
    public_party.participants.remove(guest_user)
    
    response = client.post(reverse('join_watch_party'), {'room_code': 'PUB123'})
    
    public_party.refresh_from_db()
    if guest_user in public_party.participants.all():
        print("PASS: Guest auto-joined via room code POST.")
    else:
        print("FAIL: Guest failed to auto-join via room code POST.")

    # Cleanup
    public_party.delete()
    private_party.delete()
    print("Tests completed.")

if __name__ == "__main__":
    run_tests()
