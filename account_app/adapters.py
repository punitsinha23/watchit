from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import perform_login
from allauth.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from django.contrib import messages
import uuid

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        # Ignore if user is already authenticated
        if request.user.is_authenticated:
            return

        # Attempt to find user by email
        if sociallogin.is_existing:
            return

        email = sociallogin.user.email
        if not email:
            return

        try:
            user = get_user_model().objects.get(email=email)
            # If user exists, connect this social account to the existing user
            sociallogin.connect(request, user)
        except get_user_model().DoesNotExist:
            pass

    def populate_user(self, request, sociallogin, data):
        """
        Hook that can be used to further populate the user instance.
        Here we generate a unique username if the default one is taken.
        """
        user = super().populate_user(request, sociallogin, data)
        username = user.username
        
        # Check if username exists, if so, append a random string
        if get_user_model().objects.filter(username=username).exists():
           user.username = f"{username}_{uuid.uuid4().hex[:8]}"
           
        return user
