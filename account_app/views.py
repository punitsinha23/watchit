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




api_key = '593db72e'

def signup_view(request):
    if request.method == "POST":
        form = myform(request.POST)

        # Check if email already exists BEFORE form validation
        email = request.POST.get("email")
        if User.objects.filter(email=email).exists():
            messages.error(request, "User with this email already exists.")
            return redirect(reverse('signup'))

        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # User will be inactive until verified
            user.save()
            messages.success(request, "Sign-up successful. Please verify your email.")
            return redirect(reverse('verify'))  # Redirect to email verification page

    else:
        form = myform()  # Empty form for GET request

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
                movies.append(data)  
   
    context = {
        'username': username, 
        'movies': movies
    }
    
    return render(request, 'user.html', context)


def search(request):
    if not request.user.is_authenticated:
        return redirect('signup') 
    username = request.user.username
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
                return render(request, 'user_dashboard.html', {'movie_data': movie_data, 'error': error, 'username': username})

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

    return render(request, 'user_dashboard.html', {'movie_data': movie_data, 'error': error, 'username': username})

@login_required
def watchlist_view(request):
    username = request.user.username

    if request.method == "POST" and 'remove_from_watchlist' in request.POST:
        imdb_id = request.POST.get('imdb_id')
        Watchlist.objects.filter(user=request.user, imdb_id=imdb_id).delete()
        messages.success(request, "Movie removed from your watchlist.")

    watchlist = Watchlist.objects.filter(user=request.user)
    return render(request, 'watchlist.html', {'watchlist': watchlist, 'username': username})


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