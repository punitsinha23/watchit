import os
import sys
import django
from django.db import IntegrityError, transaction

# Setup Django
sys.path.append(r'c:\Users\punit\watchit\watchit')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'watchit.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.admin.models import LogEntry
from account_app.models import Watchlist, PasswordResetToken

def debug_delete(username):
    try:
        user = User.objects.get(username=username)
        print(f"Found user: {user.id} - {user.username}")
    except User.DoesNotExist:
        print(f"User {username} not found. Listing first 5 users:")
        for u in User.objects.all()[:5]:
            print(f"- {u.username}")
        return

    # Check related objects
    print(f"Watchlist items: {Watchlist.objects.filter(user=user).count()}")
    print(f"PasswordResetTokens: {PasswordResetToken.objects.filter(user=user).count()}")
    print(f"LogEntries: {LogEntry.objects.filter(user=user).count()}")

    print("Attempting to delete user...")
    try:
        with transaction.atomic():
            user.delete()
        print("User deleted successfully.")
    except Exception as e:
        print(f"Error deleting user: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug_delete(sys.argv[1])
    else:
        # Default to finding a user to test - BE CAREFUL, maybe just list?
        print("Please provide a username to test deletion. Usage: python debug_delete_user.py <username>")
        print("Existing users:")
        for u in User.objects.all()[:5]:
            print(f"- {u.username}")
