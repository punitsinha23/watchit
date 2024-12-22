from django.shortcuts import render
import requests


api_key = '593db72e'

def base(request):

    return render(request, 'base.html')



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
            error = str(e)

    return render(request, 'dashboard.html', {'movie_data': movie_data, 'error': error})
