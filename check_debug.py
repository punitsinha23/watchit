import os
import sys
from pathlib import Path

# Setup Django
sys.path.append(r'c:\Users\punit\watchit\watchit')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'watchit.settings')
import django
from django.conf import settings

django.setup()

print(f"DEBUG: {settings.DEBUG}")
print(f"STATIC_URL: {settings.STATIC_URL}")
print(f"STATIC_ROOT: {settings.STATIC_ROOT}")
print(f"STATICFILES_DIRS: {settings.STATICFILES_DIRS}")
