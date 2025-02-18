from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in

@receiver(post_save, sender=get_user_model())
def send_welcome_email(sender, instance, created, **kwargs):
    # Only send email if the user was just created and is inactive (not yet verified)
    if created and not instance.is_active:
        # Generate the verification link
        uid = urlsafe_base64_encode(force_bytes(instance.pk))
        token = default_token_generator.make_token(instance)
        verify_url = f"http://127.0.0.1:8000{reverse('verify_email', args=[uid, token])}"

        # Send the verification email
        send_mail(
            subject="Welcome to Watchit!",
            message=f"Hi {instance.email}, welcome to Watchit! Please verify your email by clicking the link below:\n\n{verify_url}",
            from_email="punitsinha495@gmail.com",  
            recipient_list=[instance.email],
            fail_silently=False
        )
