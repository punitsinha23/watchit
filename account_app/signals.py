from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

# NOTE: The verification email is sent directly in signup_view using request.build_absolute_uri().
# This signal has been intentionally disabled to avoid sending duplicate verification emails
# to every new user. If you need post-save side effects for new users (e.g., creating a Profile
# model), add them here.

# Example of a safe post-save signal (no email):
# @receiver(post_save, sender=get_user_model())
# def create_user_profile(sender, instance, created, **kwargs):
#     if created:
#         UserProfile.objects.create(user=instance)
