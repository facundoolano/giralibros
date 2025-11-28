from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect

from books.models import OfferedBook


def login(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # authenticate() will use our EmailBackend
        user = authenticate(request, username=email, password=password)

        if user is not None:
            auth_login(request, user)
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)
        else:
            error = 'Email/usuario o contraseña incorrectos'
            return render(request, 'login.html', {'error': error})

    return render(request, 'login.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        # TODO: Implement registration logic with email confirmation
        # For now, just redirect back to login
        return redirect('login')

    return redirect('login')


def logout(request):
    auth_logout(request)
    return redirect('login')


@login_required
def home(request):
    # Get books available in user's locations with already_requested annotation
    offered_books = OfferedBook.objects.for_user(request.user)

    return render(request, "home.html", {
        "offered_books": offered_books,
        "user": request.user,
    })
