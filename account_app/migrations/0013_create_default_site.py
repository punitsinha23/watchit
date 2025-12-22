from django.db import migrations
from django.conf import settings


def create_default_site(apps, schema_editor):
    """Create default Site object if it doesn't exist."""
    Site = apps.get_model('sites', 'Site')
    
    # Check if site with SITE_ID exists
    if not Site.objects.filter(pk=settings.SITE_ID).exists():
        Site.objects.create(
            pk=settings.SITE_ID,
            domain='watchit-eta.vercel.app',
            name='WATCHIT'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('account_app', '0012_alter_watchlist_options_passwordresettoken_is_used_and_more'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(create_default_site, migrations.RunPython.noop),
    ]
