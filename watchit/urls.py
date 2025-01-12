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

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', watchit_views.base, name='base'),  
    path('dashboard/', watchit_views.dashboard, name='dashboard'),  
    path('signup/', account_views.signup_view, name='signup'),
    path('login/', account_views.login_view, name='login'),
    path('logout/', account_views.logout_view, name='logout'),
    path('user/<str:username>/', account_views.user, name='user'),
    path('dashboard/<str:username>/', account_views.search, name='dashboard')

]
