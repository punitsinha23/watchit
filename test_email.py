import os
import django
from django.core.mail import send_mail
from django.conf import settings
import sys

# Setup Django standalone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'watchit.settings')
django.setup()

def test_email():
    print(f"Testing email configuration...")
    print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    # Don't print the actual password for security, but check if it's set
    pwd_len = len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else 0
    print(f"EMAIL_HOST_PASSWORD length: {pwd_len}")
    
    if pwd_len == 0:
        print("ERROR: EMAIL_HOST_PASSWORD is empty or not loaded.")
        return

    recipient = settings.EMAIL_HOST_USER
    print(f"\nAttempting to send test email to {recipient}...")

    try:
        send_mail(
            subject='WatchIt SMTP Test',
            message='This is a test email from your Django application. If you see this, your email configuration is working!',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        print("\nSUCCESS! Email sent successfully.")
    except Exception as e:
        print(f"\nFAILURE! Could not send email.")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print("\nTroubleshooting Tips:")
        print("1. Ensure 'Less secure app access' is ON (if not using 2FA).")
        print("2. If 2FA is ON, you MUST use an App Password.")
        print("3. Check for typos in your .env file.")

if __name__ == "__main__":
    test_email()
