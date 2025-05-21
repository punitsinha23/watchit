from django.shortcuts import render,redirect
import requests
from .data import keyword, shows, top_100_movies, animes , anime_ids
from django.core.paginator import Paginator




api_key = '593db72e'

def base(request):
    shows_list = []
    movies = []
    Animes = []
    
    for title in keyword:
        url = f"http://www.omdbapi.com/?apikey={api_key}&t={title}" 
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

    for title in animes:
        url = f"http://www.omdbapi.com/?apikey={api_key}&t={title}"
        response = requests.get(url)

        if response.status_code == 200: 
            data = response.json()
            if data.get("Response") == "True":
                Animes.append(data)            


    
    context = {
        'movies': movies,
        'shows' : shows_list,
        'Animes': Animes,
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

    return render(request, 'dashboard.html', {'movie_data': movie_data, 'error': error})




def movie_view(request):
    movies_per_page = 28

   
    page_number = request.GET.get('page', 1)

    
    paginator = Paginator(top_100_movies, movies_per_page)

  
    page_obj = paginator.get_page(page_number)

   
    movies = []
    
   
    for movie_id in page_obj.object_list:
        url = f"http://www.omdbapi.com/?apikey={api_key}&i={movie_id}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get("Response") == "True":
                movies.append(data)

    
    return render(request, 'movies.html', {'page_obj': page_obj, 'movies': movies})


def anime_view(request):
    movies_per_page = 28

   
    page_number = request.GET.get('page', 1)

    
    paginator = Paginator(anime_ids, movies_per_page)

  
    page_obj = paginator.get_page(page_number)

   
    animes = []
    
   
    for id in page_obj.object_list:
        url = f"http://www.omdbapi.com/?apikey={api_key}&i={id}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data.get("Response") == "True":
                animes.append(data)
    print(animes)
    
    return render(request, 'anime.html', {'page_obj': page_obj, 'animes': animes})


def about_view(request):
    return render(request , 'about.html')    
