from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from .forms import myform, loginform
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required 
from watchit_app.views import dashboard 
import requests

api_key = '593db72e'

def signup_view(request):
    if request.method == "POST":
        form = myform(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  
            messages.success(request, "Signup successful!")
            return redirect(reverse('user', kwargs={'username': user.username}))  
        else:
            form.add_error("email", "The email address could not be verified.")
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
                    return redirect('user', username=user.username) 
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
def user(request, username):
    if request.user.username != username:  
        messages.error(request, "You do not have permission to access this page.")
        return redirect('login')  
    
    keyword = [
    "The Shawshank Redemption", "The Dark Knight", "The Godfather", "Pulp Fiction", "The Matrix",
    "Forrest Gump", "The Lion King", "Inception", "Gladiator", "The Lord of the Rings: The Fellowship of the Ring",
    "Fight Club", "The Prestige", "The Green Mile", "Interstellar", "The Social Network",
    "Schindler's List", "The Departed", "Whiplash", "Parasite", "The Terminator",
    "Back to the Future", "The Good, the Bad and the Ugly", "12 Angry Men", "Citizen Kane", "Jaws",
    "Star Wars: Episode V - The Empire Strikes Back", "Pulp Fiction", "Se7en", "The Silence of the Lambs",
    "The Revenant", "The Wolf of Wall Street", "Memento", "La La Land", "The Grand Budapest Hotel",
    "Goodfellas", "Oldboy", "WALL-E", "Her", "Arrival", "The Pianist", "The Dark Knight Rises",
    "Spider-Man: Into the Spider-Verse", "The Truman Show", "Blade Runner 2049", "Coco", "Your Name",
    "Joker", "Avengers: Endgame", "Mad Max: Fury Road", "Zootopia"
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

@login_required
def search(request , username):
    movie_data = None
    error = None
    if request.method == "POST":
        movie_title = request.POST.get('title')

        if not movie_title:
            error = "Please enter a movie title."
            return render(request, 'dashboard.html', {'movie_data': movie_data, 'error': error})

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

    return render(request, 'user_dashboard.html', {'movie_data': movie_data, 'error': error , 'username':username})


