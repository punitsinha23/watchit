from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponse
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from datetime import timedelta
from django.core.mail import send_mail

import requests

from .forms import myform, loginform, PasswordResetRequestForm
from .models import Watchlist, PasswordResetToken


api_key = '24a15e19'


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
            messages.success(request, "Sign-up successful. Please verify your email.")
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

@login_required
def user(request):
    # Fetch a few items for each category (e.g., 10 items each)
    # We randomize to keep it fresh or just take the first N
    
    # helper to fetch list
    def get_data(source_list, limit=50):
        results = []
        for item in source_list[:limit]: # simple slicing for now
            # if item is a title (str), use title=item
            # if item is an ID (starts with tt), use imdb_id=item
            kwargs = {}
            if item.startswith('tt'):
                kwargs['imdb_id'] = item
            else:
                kwargs['title'] = item
            
            data = fetch_omdb_data(**kwargs)
            if data and data.get('Poster') != 'N/A':
                results.append(data)
        return results

    movies_data = get_data(top_100_movies)
    anime_data = get_data(animes)
    shows_data = get_data(shows)

    return render(request, 'user.html', {
        'movies': movies_data,
        'anime': anime_data,
        'shows': shows_data,
        'display_name': request.user.username
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
    
    # Redirect to the watchlist page as requested
    return redirect('watchlist')


@login_required
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

    return render(request, 'user_dashboard.html', {
        'movie_data': movie_data,
        'error': error
    })


@login_required
def watchlist_view(request):
    if request.method == "POST":
        imdb_id = request.POST.get('imdb_id')
        Watchlist.objects.filter(user=request.user, imdb_id=imdb_id).delete()
        messages.success(request, "Movie removed from watchlist.")

    watchlist = Watchlist.objects.filter(user=request.user)
    return render(request, 'watchlist.html', {'watchlist': watchlist})


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


def request_password_reset(request):
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email=email).first()

            if user:
                PasswordResetToken.objects.update_or_create(
                    user=user,
                    defaults={'token': get_random_string(32)}
                )

                token = PasswordResetToken.objects.get(user=user).token
                reset_link = request.build_absolute_uri(
                    reverse('reset_password', args=[token])
                )

                send_mail(
                    "Password Reset",
                    f"Reset your password: {reset_link}",
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                )

            messages.success(request, "If the email exists, a reset link was sent.")
            return redirect('login')
    else:
        form = PasswordResetRequestForm()

    return render(request, 'password_reset_request.html', {'form': form})


def reset_password(request, token):
    reset_token = get_object_or_404(PasswordResetToken, token=token)

    if not reset_token.is_valid():
        reset_token.delete()
        messages.error(request, "Reset link expired.")
        return redirect('login')

    if request.method == "POST":
        password = request.POST['password']
        confirm = request.POST['confirm_password']

        if password != confirm:
            messages.error(request, "Passwords do not match.")
        else:
            user = reset_token.user
            user.password = make_password(password)
            user.save()
            reset_token.delete()

            messages.success(request, "Password reset successful.")
            return redirect('login')

    return render(request, 'reset_password.html')

def remove_from_watchlist(request, imdb_id):
    try:
        watchlist_item = Watchlist.objects.get(user=request.user, imdb_id=imdb_id)
        watchlist_item.delete()
        messages.success(request, "Movie removed from watchlist.")
    except Watchlist.DoesNotExist:
        messages.error(request, "Movie not found in watchlist.")
    return redirect('watchlist')
