import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'watchit.settings')
django.setup()

from account_app.models import PasswordResetToken

print("Deleting all existing password reset tokens to clear invalid data...")
count, _ = PasswordResetToken.objects.all().delete()
print(f"Deleted {count} tokens.")
