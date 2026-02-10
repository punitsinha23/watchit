from django.core.management.base import BaseCommand
from django.utils import timezone
from watchit_app.models import WatchParty
from datetime import timedelta

class Command(BaseCommand):
    help = 'Deletes watch party rooms older than 24 hours'

    def handle(self, *args, **options):
        expiry_time = timezone.now() - timedelta(hours=24)
        expired_parties = WatchParty.objects.filter(created_at__lt=expiry_time)
        count = expired_parties.count()
        expired_parties.delete()
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} expired watch parties.'))
