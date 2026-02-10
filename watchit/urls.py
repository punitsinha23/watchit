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
from django.urls import path, include
from watchit_app import views as watchit_views
from account_app import views as account_views
from . import settings 
from django.contrib.auth import views as auth_views
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', watchit_views.base, name='base'),
    path('fetch-more/', watchit_views.fetch_more_items, name='fetch_more'),
    path('api/trial-status/', watchit_views.check_trial_status, name='trial_status'),
    path('about/', watchit_views.about_view , name='about'),
    path('dashboard/', watchit_views.dashboard, name='dashboard'),  
    path('watch/<str:imdb_id>/', watchit_views.detail_view, name='detail'),
    path('signup/', account_views.signup_view, name='signup'),
    path('verify/<uidb64>/<token>/', account_views.verify_email, name='verify_email'),
    path('verify/', account_views.verify, name='verify'),
    path('accounts/login/', account_views.login_view, name='login'),
    path('logout/', account_views.logout_view, name='logout'),
    path('forgot-password/', account_views.forgot_password, name='forgot_password'),
    path('reset-password/<str:token>/', account_views.reset_password, name='reset_password'),
    path('account/profile/', account_views.user, name='user'),
    path('account/profile/dashboard', account_views.search, name='user_dashboard'),
    path('account/profile/watchlist/add/', account_views.add_to_watchlist, name='add_to_watchlist'),
    path('account/profile/watchlist/remove/<str:imdb_id>/', account_views.remove_from_watchlist, name='remove_from_watchlist'),
    path('account/profile/watchit', account_views.watchlist_view , name='watchlist'),
    
    # Watch Party URLs
    path('party/create/<str:imdb_id>/', watchit_views.create_watch_party, name='create_watch_party'),
    path('party/join/', watchit_views.join_watch_party, name='join_watch_party'),
    path('party/room/<str:room_code>/', watchit_views.party_room, name='party_room'),
    path('party/api/status/<str:room_code>/', watchit_views.api_party_status, name='api_party_status'),
    path('party/api/update/<str:room_code>/', watchit_views.api_party_update, name='api_party_update'),
    path('party/api/chat/<str:room_code>/', watchit_views.api_party_chat, name='api_party_chat'),
    
    # New Room Management & Approval URLs
    path('party/waiting/<str:room_code>/', watchit_views.waiting_room, name='waiting_room'),
    path('party/api/check-approval/<str:room_code>/', watchit_views.api_check_approval, name='api_check_approval'),
    path('party/api/handle-request/<str:room_code>/', watchit_views.api_handle_join_request, name='api_handle_join_request'),
    path('party/delete/<str:room_code>/', watchit_views.delete_party, name='delete_party'),
] 




if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
