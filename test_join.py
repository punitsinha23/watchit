import os
import django
import sys

# Setup Django environment
sys.path.append(r'c:\Users\punit\watchit\watchit')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'watchit.settings')
django.setup()

from django.contrib.auth.models import User
from watchit_app.models import WatchParty

# let's create a user
user, _ = User.objects.get_or_create(username='tester', email='tester@example.com')
if not user.password:
    user.set_password('password123')
    user.is_active = True
    user.save()

party, _ = WatchParty.objects.get_or_create(room_code='TST123', host=user, imdb_id='tt1234567')

print(f"Room {party.room_code} Host: {party.host.username}")

from django.test import Client
c = Client()
c.login(username='tester', password='password123')

# Try party room
response = c.get(f'/party/{party.room_code}/')
print(f"Host GET /party/TST123/ response status: {response.status_code}")
if response.status_code == 302:
    print(f"Redirected to: {response.url}")

# Try joining through join_watch_party
response = c.post('/party/join/', {'room_code': 'TST123'})
print(f"Host POST /party/join/ response status: {response.status_code}")
if response.status_code == 302:
    print(f"Redirected to: {response.url}")

