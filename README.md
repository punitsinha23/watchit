# WatchIt - Streaming Website

**WatchIt** is a Django-based streaming website where users can watch movies and TV shows online. The platform is designed to be easy to use and provides a seamless streaming experience for users.

## Features

- **User Authentication**: Sign up, login, and logout functionalities for users.
- **Content Streaming**: Watch movies and TV shows directly from the platform.
- **Search Functionality**: Easily search for movies, series, or episodes.
- **Responsive Design**: Mobile and desktop-friendly layout.
- **Admin Panel**: Manage content, users, and settings via Django's admin panel.
- **Watchlist**: Users can add movies and shows to their personal watchlist.
- **Ratings & Reviews**: Users can rate and leave reviews for movies or shows.

## Tech Stack

- **Backend**: Django, Django REST Framework
- **Frontend**: HTML, CSS, JavaScript
- **Database**: SQLite (default) or PostgreSQL
- **Authentication**: Django's built-in authentication system
- **Streaming**: Vidsrc for movie streaming

## Installation

### Requirements

- Python 3.x
- Django 4.x or above
- PostgreSQL (if you're using it as a database)
- Celery (optional, for asynchronous tasks)

### Steps to Set Up

1. Clone the repository:
   git clone https://github.com/your-username/watchit.git
   cd watchit
2. Create and activate a virtual environment:
    python3 -m venv venv
    venv/bin/activate

3. Install required dependencies:
    pip install -r requirements.txt
    Set up the database:

4. connect to sqlite
    python manage.py migrate
    Create a superuser (for accessing the admin panel):

5. createsuperuser
    python manage.py createsuperuser
    Run the development server:

##Usage

User Registration: Visit the registration page to create a new account.
Search: Use the search bar to find your favorite movies and shows.
Watch: Click on any movie or TV show to start streaming.
Admin Panel: Access the admin panel by navigating to http://127.0.0.1:8000/admin/ to manage users, content, and more.
Contributing

##Fork the repository
Create your branch (git checkout -b feature/your-feature)
Commit your changes (git commit -m 'Add new feature')
Push to the branch (git push origin feature/your-feature)
Create a new Pull Request

##License
This project is licensed under the MIT License - see the LICENSE file for details.

##Acknowledgments
Vidsrc for providing the movie streaming API.
Django for the awesome web framework.

