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
        "Inception",
        "Interstellar",
        "Se7en",
        "Parasite",
        "The truman show",
        "Whiplash",
        "Grave of the Fireflies",
        "Avengers: Endgame",
        "The Great Dictator",
        "Coco",
        "inside out 2",
        "Oldboy",
        "Avengers: Infinity War",
        "The Wolf of Wall Street",
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
        "squid game",
        "la la land",
        "harry potter",
        
    ]

    shows = [
         "Breaking Bad",
        "Better call saul",
        "The Wire",
        "Stranger Things",
        "Friends",
        "The Office (US)",
        "Sherlock",
        "Narcos",
        "Chernobyl",
        "Black Mirror",
        "Game of Thrones",
        "The Mandalorian",
        "Rick and Morty",
        "True Detective",
        "Peaky Blinders",
        "The Simpsons",
        "House of Cards",
        "Money Heist",
        "The Witcher",
        "Fleabag",
        "Vikings",
        "The Boys",
        "The Queen's Gambit",
        "How I Met Your Mother",
        "The Haunting of Hill House",
        "Dark",
        "Supernatural",
        "The Marvelous Mrs. Maisel",
        "BoJack Horseman"
        ]
    
    shows_list = []
    movies = []
    
    for title in keyword:
        url = f"http://www.omdbapi.com/?apikey={api_key}&t={title}"  # Search for individual movies by title
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("Response") == "True":
                movies.append(data) 
    
    for title in shows:
        url = f"http://www.omdbapi.com/?apikey={api_key}&t={title}"
        response = requests.get(url)

        if response.status_code == 200: 
            data = response.json()
            if data.get("Response") == "True":
                shows_list.append(data)


    
    context = {
        'movies': movies,
        'shows' : shows_list,
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

def about_view(request):
    return render(request , 'about.html')    
