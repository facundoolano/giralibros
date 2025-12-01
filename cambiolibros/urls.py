"""
URL configuration for cambiolibros project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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

from books import views

urlpatterns = [
    path('', views.home, name='home'),
    path('my/offered/', views.my_offered_books, name='my_offered'),
    path('my/wanted/', views.my_wanted_books, name='my_wanted'),
    path('books/<int:book_id>/request-exchange/', views.request_exchange, name='request_exchange'),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('verify/<str:uidb64>/<str:token>/', views.verify_email, name='verify_email'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('logout/', views.logout, name='logout'),
    path('admin/', admin.site.urls),
]
