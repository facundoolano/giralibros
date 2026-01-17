"""
URL configuration for giralibros project.

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
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from books import views

urlpatterns = [
    path('', views.list_books, name='home'),
    path('my/offered/', views.my_offered_books, name='my_offered'),
    path('my/offered/<int:book_id>/edit/', views.my_offered_books, name='edit_offered_book'),
    path('my/offered/<int:book_id>/delete/', views.delete_offered_book, name='delete_offered_book'),
    path('my/offered/<int:book_id>/trade/', views.trade_offered_book, name='trade_offered_book'),
    path('my/wanted/', views.my_wanted_books, name='my_wanted'),
    path('my/wanted/<int:book_id>/delete/', views.delete_wanted_book, name='delete_wanted_book'),
    path('books/<int:book_id>/request-exchange/', views.request_exchange, name='request_exchange'),
    path('books/<int:book_id>/upload-photo/', views.upload_book_photo, name='upload_book_photo'),
    path('about/', views.about, name='about'),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('verify/<str:uidb64>/<str:token>/', views.verify_email, name='verify_email'),
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset_request'),
    path('password-reset/done/', views.password_reset_done, name='password_reset_done'),
    path('password-reset/<str:uidb64>/<str:token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.password_reset_complete, name='password_reset_complete'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('logout/', views.logout, name='logout'),
    path('admin/', admin.site.urls),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
