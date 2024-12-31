from django.shortcuts import render,redirect
import requests
from django.contrib.auth.hashers import make_password
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.hashers import check_password

api_key = '593db72e'

def base(request):
    keyword = [
        "Fight Club",
        "Forrest Gump",
        "Inception",
        "Interstellar",
        "Se7en",
        "Parasite",
        "The Lion King",
        "Back to the Future",
        "The Pianist",
        "The Prestige",
        "Whiplash",
        "Grave of the Fireflies",
        "Avengers: Endgame",
        "The Great Dictator",
        "Coco",
        "Your Name",
        "Joker",
        "WALL-E",
        "Oldboy",
        "Avengers: Infinity War",
        "The Wolf of Wall Street",
        "Memento",
        "The Truman Show",
        "The Social Network",
        "Eternal Sunshine of the Spotless Mind",
        "Taxi Driver",
        "Blade Runner 2049",
        "Toy Story",
        "3 Idiots",
        "Up",
        "Inside Out",
        "La La Land",
        "The Pursuit of Happyness",
        "Zootopia",
    ]
    
    # Initialize an empty list for storing movie data
    movies = []
    
    # Loop through the movie titles and fetch data from OMDb API
    for title in keyword:
        url = f"http://www.omdbapi.com/?apikey={api_key}&t={title}"  # Search for individual movies by title
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("Response") == "True":
                movies.append(data)  # Append movie data to the list
    
    # Pass the movie data to the template
    context = {
        'movies': movies,
    }

    return render(request, 'base.html', context)

def dashboard(request):
    movie_data = None
    error = None

    if request.method == "POST":
        movie_title = request.POST.get('title')

        if not movie_title:
            error = "Please enter a movie title."
            return render(request, 'dashboard.html', {'movie_data': movie_data, 'error': error})

        try:
            api_url = f"http://www.omdbapi.com/?apikey={api_key}&s={movie_title}"  # Search for movies by title
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

    return render(request, 'dashboard.html', {'movie_data': movie_data, 'error': error})
