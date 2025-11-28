from django.conf import settings
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

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
    2. Inactive user is created (is_active=False)
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
            # Create inactive user pending email verification
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            # Generate verification token and URL
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Build absolute URL for verification link
            verification_path = reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
            verification_url = request.build_absolute_uri(verification_path)

            if settings.DEBUG:
                # In development, print verification link to console
                print("\n" + "="*80)
                print("EMAIL VERIFICATION LINK (Debug Mode)")
                print("="*80)
                print(f"User: {user.username} ({user.email})")
                print(f"Verification URL: {verification_url}")
                print("="*80 + "\n")
            else:
                # FIXME: Implement send verification email
                # send_verification_email(user, verification_url)
                pass

            # Show confirmation page
            return render(request, 'registration_confirmation.html', {
                'email': user.email,
            })
        else:
            # If form is invalid, re-render login page with errors
            login_form = EmailOrUsernameAuthenticationForm(request)
            return render(request, 'login.html', {
                'login_form': login_form,
                'register_form': form,
            })

    return redirect('login')


def verify_email(request, uidb64, token):
    """
    Verify user's email address using the token sent via email.
    On success, activate the user and log them in.
    """
    try:
        # Decode the user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        # Valid token - activate user and log them in
        user.is_active = True
        user.save()
        auth_login(request, user)

        # Redirect to profile completion (to be implemented)
        # For now, redirect to home
        return redirect('home')
    else:
        # Invalid or expired token
        return render(request, 'verification_failed.html')


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
