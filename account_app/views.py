from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.contrib import messages

from django.urls import reverse
from django.http import HttpResponse
from django.conf import settings

from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str, force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from datetime import timedelta


import requests
import uuid
from django.utils.timezone import now
from datetime import timedelta
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password

from .forms import myform, loginform
from .models import Watchlist, PasswordResetToken
from watchit_app.models import WatchParty


from decouple import config
api_key = config('OMDB_API_KEY')


def signup_view(request):
    if request.method == "POST":
        form = myform(request.POST)
        email = request.POST.get("email")

        if User.objects.filter(email=email).exists():
            messages.error(request, "User with this email already exists.")
            return redirect('signup')

        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            # Send verification email
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verify_link = request.build_absolute_uri(
                reverse('verify_email', args=[uid, token])
            )

            send_mail(
                "Verify Your Email - WATCHIT",
                f"Click the link to verify your email and activate your account: {verify_link}",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

            messages.success(request, "Sign-up successful. Please check your email to verify your account.")
            return redirect('verify')
    else:
        form = myform()

    return render(request, 'signup.html', {'form': form})


def login_view(request):
    if request.method == "POST":
        form = loginform(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')

            try:
                user_obj = User.objects.get(email=email)
                user = authenticate(
                    request,
                    username=user_obj.username,
                    password=password
                )

                if user:
                    login(request, user)
                    messages.success(request, "You have successfully logged in.")
                    return redirect('user')
                else:
                    messages.error(request, "Invalid email or password.")
            except User.DoesNotExist:
                messages.error(request, "User with this email does not exist.")
    else:
        form = loginform()

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('base')


from watchit_app.data import top_100_movies, animes, shows
from watchit_app.views import fetch_omdb_data
import random

from concurrent.futures import ThreadPoolExecutor, as_completed

@login_required
@cache_control(private=True, max_age=3600)
def user(request):
    # Fetch active parties
    hosted_parties = WatchParty.objects.filter(host=request.user, is_active=True)
    joined_parties = request.user.joined_parties.filter(is_active=True).exclude(host=request.user)
    
    # Fetch all active public parties (excluding ones the user is already in)
    public_parties = WatchParty.objects.filter(is_active=True, is_private=False).exclude(host=request.user).exclude(participants=request.user).order_by('-created_at')

    # Fetch watchlist
    watchlist_items = Watchlist.objects.filter(user=request.user).order_by('-id')

    return render(request, 'user.html', {
        'display_name': request.user.username,
        'hosted_parties': hosted_parties,
        'joined_parties': joined_parties,
        'public_parties': public_parties,
        'watchlist': watchlist_items,
    })


@login_required
def add_to_watchlist(request):
    """
    Dedicated view to add items to watchlist and redirect to Watchlist page.
    """
    if request.method == "POST":
        imdb_id = request.POST.get('imdb_id')
        print(f"Watchlist Add Request: {request.POST}") # DEBUG LOG
        
        # Check if item exists to avoid duplicates
        if not Watchlist.objects.filter(user=request.user, imdb_id=imdb_id).exists():
            Watchlist.objects.create(
                user=request.user,
                imdb_id=imdb_id,
                movie_title=request.POST.get('title'),
                movie_year=request.POST.get('year'),
                poster=request.POST.get('poster')
            )
            messages.success(request, "Added to your watchlist!")
        else:
            messages.info(request, "Already in your watchlist.")
    
    # Stay on the current page after adding and show a message
    return redirect(request.META.get('HTTP_REFERER', 'user'))


def search(request):
    movie_data = None
    error = None

    if request.method == "POST":
        # Fallback for legacy search view additions if any
        if 'add_to_watchlist' in request.POST:
            return add_to_watchlist(request)

        movie_title = request.POST.get('title')
        if not movie_title:
            error = "Please enter a movie title."
        else:
            api_url = f"http://www.omdbapi.com/?apikey={api_key}&s={movie_title}"
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json()
                if data.get("Response") == "True":
                    movie_data = data.get("Search", [])
                else:
                    error = data.get("Error")

    watchlist_ids = set()
    if request.user.is_authenticated:
        watchlist_ids = set(Watchlist.objects.filter(user=request.user).values_list('imdb_id', flat=True))

    return render(request, 'user_dashboard.html', {
        'movie_data': movie_data,
        'error': error,
        'watchlist_ids': watchlist_ids
    })





def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = get_user_model().objects.get(pk=uid)

        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save()
            login(request, user)
            return redirect('user')
        return HttpResponse("Invalid token.")

    except Exception:
        return HttpResponse("Invalid verification link.")


def verify(request):
    return render(request, 'verify.html')


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email')
        user = User.objects.filter(email=email).first()

        if user:
            # Create or update token
            PasswordResetToken.objects.update_or_create(
                user=user,
                defaults={'token': uuid.uuid4(), 'created_at': now()}
            )
            
            token_obj = PasswordResetToken.objects.get(user=user)
            reset_link = request.build_absolute_uri(
                reverse('reset_password', args=[str(token_obj.token)])
            )

            send_mail(
                "Reset Your Password - WATCHIT",
                f"Click the link to reset your password: {reset_link}",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

        # Always show success message for security (prevent email enumeration)
        messages.success(request, "If an account exists with this email, a reset link has been sent.")
        return redirect('forgot_password') 

    return render(request, 'forgot_password.html')


def reset_password(request, token):
    try:
        reset_token = PasswordResetToken.objects.get(token=token)
    except (PasswordResetToken.DoesNotExist, ValueError):
        messages.error(request, "Invalid or expired reset link.")
        return redirect('login')

    if not reset_token.is_valid():
        reset_token.delete()
        messages.error(request, "Link has expired.")
        return redirect('login')

    if request.method == "POST":
        password = request.POST.get('password')
        confirm = request.POST.get('confirm_password')

        if password != confirm:
            messages.error(request, "Passwords do not match.")
        else:
            user = reset_token.user
            user.set_password(password)
            user.save()
            reset_token.delete() # Consume token

            messages.success(request, "Password reset successful! You can now log in.")
            return redirect('login')

    return render(request, 'reset_password.html')


def remove_from_watchlist(request, imdb_id):
    try:
        watchlist_item = Watchlist.objects.get(user=request.user, imdb_id=imdb_id)
        watchlist_item.delete()
        messages.success(request, "Movie removed from watchlist.")
    except Watchlist.DoesNotExist:
        messages.error(request, "Movie not found in watchlist.")
    return redirect('user')
