from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from books.forms import EmailOrUsernameAuthenticationForm, RegistrationForm
from books.models import OfferedBook


def login(request):
    if request.user.is_authenticated:
        return redirect('home')

    login_form = EmailOrUsernameAuthenticationForm(request, data=request.POST or None)
    register_form = RegistrationForm()

    if request.method == 'POST':
        if login_form.is_valid():
            user = login_form.get_user()
            auth_login(request, user)
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)

    return render(request, 'login.html', {
        'login_form': login_form,
        'register_form': register_form,
    })


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
