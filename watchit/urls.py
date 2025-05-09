"""
URL configuration for watchit project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from watchit_app import views as watchit_views
from account_app import views as account_views
from . import settings 
from django.contrib.auth import views as auth_views
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', watchit_views.base, name='base'),
    path('movies/', watchit_views.movie_view, name='movies'),
    path('anime/', watchit_views.anime_view , name='anime' ),
    path('about/', watchit_views.about_view , name='about'),  
    path('dashboard/', watchit_views.dashboard, name='dashboard'),  
    path('signup/', account_views.signup_view, name='signup'),
    path('verify/<uidb64>/<token>/', account_views.verify_email, name='verify_email'),
    path('verify/', account_views.verify, name='verify'),
    path('accounts/login/', account_views.login_view, name='login'),
    path('logout/', account_views.logout_view, name='logout'),
    path("password_reset/", account_views.request_password_reset, name="password_reset_request"),
    path("reset/<str:token>/", account_views.reset_password, name="reset_password"),
    path('account/profile/', account_views.user, name='user'),
    path('account/profile/dashboard', account_views.search, name='dashboard'),
    path('account/profile/watchit', account_views.watchlist_view , name='watchlist')
    
] 




if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
