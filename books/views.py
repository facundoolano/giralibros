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
    """
    Handle user registration.

    TODO: In production, this should send an email verification link instead of
    immediately creating an active user. The flow should be:
    1. User submits registration form
    2. Inactive user is created
    3. Email with verification link is sent
    4. User clicks verification link
    5. User is activated and can log in
    6. On first login, user is redirected to profile completion
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            # Create the user (in production, set is_active=False until email verified)
            user = form.save()

            # Auto-login for convenience (in production, redirect to "check your email" page)
            auth_login(request, user)

            # Redirect to profile completion (to be implemented)
            # For now, redirect to home
            return redirect('home')
        else:
            # If form is invalid, re-render login page with errors
            login_form = EmailOrUsernameAuthenticationForm(request)
            return render(request, 'login.html', {
                'login_form': login_form,
                'register_form': form,
            })

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
