from django.shortcuts import render, redirect
from .forms import myform, loginform
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required 
import requests
from .models import Watchlist
from django.http import HttpResponse
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from .forms import PasswordResetRequestForm
from .models import PasswordResetToken
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from datetime import timedelta
<<<<<<< HEAD

=======
>>>>>>> 232b73124b94c537aea1ed2698f86d9ffce2a163


from decouple import config

api_key = '24a15e19'

def signup_view(request):
    if request.method == "POST":
        form = myform(request.POST)

       
        email = request.POST.get("email")
        if User.objects.filter(email=email).exists():
            messages.error(request, "User with this email already exists.")
            return redirect(reverse('signup'))

        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False 
            user.save()
            messages.success(request, "Sign-up successful. Please verify your email.")
            return redirect(reverse('verify')) 

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
                user = User.objects.get(email=email)
                user = authenticate(request, username=user.username, password=password)
                
                if user is not None:
                    login(request, user) 
                    messages.success(request, "You have successfully logged in.")
                    return redirect('user') 
                else:
                    messages.error(request, "Invalid email or password.")
            except User.DoesNotExist:
                messages.error(request, "User with this email does not exist.")
        else:
            messages.error(request, "Invalid form submission.")
    else:
        form = loginform()

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request) 
    messages.success(request, "Logged out successfully!")
    return redirect(reverse('base')) 



@login_required
def user(request):
    username= request.user.username
    
    keyword = [
    "The Shawshank Redemption", "The Dark Knight", "The Godfather", "Pulp Fiction", "The Matrix",
    "Forrest Gump", "The Lion King", "Inception", "Gladiator", "The Lord of the Rings: The Fellowship of the Ring",
    "Fight Club", "The Prestige", "The Green Mile", "Interstellar", "The Social Network",
    "Schindler's List", "The Departed", "Whiplash", "Parasite", "The Terminator",
    "Back to the Future", "The Good, the Bad and the Ugly", "12 Angry Men", "Citizen Kane", "Jaws",
    "Star Wars: Episode V - The Empire Strikes Back", "Pulp Fiction", "Se7en", "The Silence of the Lambs",
    "The Revenant", "The Wolf of Wall Street", "Memento", "La La Land", "The Grand Budapest Hotel",
    "Goodfellas", "Oldboy","Her", "Arrival", "The Pianist", "The Dark Knight Rises",
    "Spider-Man: Into the Spider-Verse", "Blade Runner 2049",
]
    
    
   
    movies = []
    
   
    for title in keyword:
        url = f"http://www.omdbapi.com/?apikey={api_key}&t={title}" 
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("Response") == "True":
<<<<<<< HEAD
                movies.append(data)

=======
                movies.append(data)  
   
>>>>>>> 232b73124b94c537aea1ed2698f86d9ffce2a163
    context = {
        'movies': movies
    }
    
    return render(request, 'user.html', context)


<<<<<<< HEAD
@login_required
def search(request):
=======
def search(request):
    if not request.user.is_authenticated:
        return redirect('signup') 
    username = request.user.username
>>>>>>> 232b73124b94c537aea1ed2698f86d9ffce2a163
    movie_data = None
    error = None
    


    if request.method == "POST":
        if 'add_to_watchlist' in request.POST:
            imdb_id = request.POST.get('imdb_id')
            title = request.POST.get('title')
            year = request.POST.get('year')
            poster = request.POST.get('poster')

            
            watchlist_item, created = Watchlist.objects.get_or_create(
                user=request.user,
                imdb_id=imdb_id,
                defaults={
                    'movie_title': title,
                    'movie_year': year,
                    'poster': poster,
                }
            )
            if created:
                messages.success(request, f"'{title}' added to your watchlist!")
            else:
                messages.info(request, f"'{title}' is already in your watchlist.")
            return redirect('watchlist')


        else:
            movie_title = request.POST.get('title')
            if not movie_title:
                error = "Please enter a movie title."
                return render(request, 'user_dashboard.html', {'movie_data': movie_data, 'error': error})

            try:
                api_url = f"http://www.omdbapi.com/?apikey={api_key}&s={movie_title}"
                response = requests.get(api_url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("Response") == "True":
                        movie_data = data.get("Search", [])
                    else:
                        error = data.get("Error", "No movies or series found matching the title.")
                else:
                    error = "Failed to fetch data from OMDb API. Please try again later."
            except Exception as e:
                error = f"An error occurred: {str(e)}"

    return render(request, 'user_dashboard.html', {'movie_data': movie_data, 'error': error})

@login_required
def watchlist_view(request):

    if request.method == "POST" and 'remove_from_watchlist' in request.POST:
        imdb_id = request.POST.get('imdb_id')
        Watchlist.objects.filter(user=request.user, imdb_id=imdb_id).delete()
        messages.success(request, "Movie removed from your watchlist.")

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
        else:
            return HttpResponse("Invalid token.") 
        
    except (TypeError, ValueError, OverflowError, user.DoesNotExist):
        return HttpResponse("Invalid verification link.")  

def verify(request):
    return render(request, 'verify.html')

def request_password_reset(request):
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = User.objects.filter(email=email).first() 
            
            if user:
                token = get_random_string(length=32)

              
                PasswordResetToken.objects.update_or_create(user=user, defaults={'token': token})

                reset_link = request.build_absolute_uri(reverse('reset_password', args=[token]))

                send_mail(
                    "Password Reset Request",
                    f"Click the link to reset your password: {reset_link}",
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )

            messages.success(request, "If the email is registered, a password reset link has been sent.")
            return redirect("login")

    else:
        form = PasswordResetRequestForm()

    return render(request, "password_reset_request.html", {"form": form})



def reset_password(request, token):
    reset_token = get_object_or_404(PasswordResetToken, token=token)

    
    if reset_token.created_at < now() - timedelta(hours=24):
        reset_token.delete()  
        messages.error(request, "This password reset link has expired.")
        return redirect("login")

    if request.method == "POST":
        new_password = request.POST["password"]
        confirm_password = request.POST["confirm_password"]

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
        else:
            reset_token.user.password = make_password(new_password)
            reset_token.user.save()
            reset_token.delete() 

            messages.success(request, "Password reset successful. You can now log in.")
            return redirect("login")

    return render(request, "reset_password.html")