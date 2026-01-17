import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'watchit.settings')
django.setup()

from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

print(f"Current settings.SITE_ID: {getattr(settings, 'SITE_ID', 'Not Set')}")

print("\n--- Existing Sites ---")
for site in Site.objects.all():
    print(f"ID: {site.id}, Domain: {site.domain}, Name: {site.name}")

print("\n--- Existing SocialApps ---")
for app in SocialApp.objects.all():
    print(f"ID: {app.id}, Provider: {app.provider}, Sites: {[s.id for s in app.sites.all()]}")
