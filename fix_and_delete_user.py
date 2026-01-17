import os
import sys
import django
from django.db import transaction

# Setup Django
sys.path.append(r'c:\Users\punit\watchit\watchit')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'watchit.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.admin.models import LogEntry
from account_app.models import Watchlist, PasswordResetToken

def fix_and_delete(username):
    try:
        user = User.objects.get(username=username)
        print(f"Found user: {user.id} - {user.username}")
    except User.DoesNotExist:
        print(f"User {username} not found.")
        return

    print("Starting manual cascade delete...")
    try:
        with transaction.atomic():
            # 1. Delete Watchlist items
            wl_count, _ = Watchlist.objects.filter(user=user).delete()
            print(f"Deleted {wl_count} Watchlist items.")

            # 2. Delete PasswordResetTokens
            # Note: Since it's OneToOne, we access directly or filter
            prt_count, _ = PasswordResetToken.objects.filter(user=user).delete()
            print(f"Deleted {prt_count} PasswordResetTokens.")

            # 3. Delete Admin LogEntries
            le_count, _ = LogEntry.objects.filter(user=user).delete()
            print(f"Deleted {le_count} LogEntries.")

            # 4. Clear M2M relations (Groups & Permissions)
            user.groups.clear()
            user.user_permissions.clear()
            print("Cleared Groups and User Permissions.")
            
            # 5. Handle Zombie Tables (allauth) via Raw SQL
            # Only if they exist. We try blindly; if table misses, ignore.
            cursor = django.db.connection.cursor()
            zombies = ['account_emailaddress', 'socialaccount_socialaccount']
            for zombie in zombies:
                try:
                    cursor.execute(f"DELETE FROM {zombie} WHERE user_id = %s", [user.id])
                    print(f"cleaned up {zombie} for user {user.id}")
                except Exception as sql_e:
                    # Table might not exist or error, usually "no such table"
                    # We can check specific error if needed, but printing is enough
                    print(f"Skipping {zombie}: {sql_e}")
            
            # 6. Finally delete the user
            user.delete()
            print(f"Successfully deleted user '{username}'.")
            
    except Exception as e:
        print(f"Error during manual deletion: {e}")
        import traceback
        traceback.print_exc() 


if __name__ == "__main__":
    if len(sys.argv) > 1:
        fix_and_delete(sys.argv[1])
    else:
        print("Usage: python fix_and_delete_user.py <username>")
