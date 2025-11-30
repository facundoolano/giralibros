from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.forms import modelformset_factory
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from books.forms import (
    EmailOrUsernameAuthenticationForm,
    OfferedBookForm,
    ProfileForm,
    RegistrationForm,
)
from books.models import ExchangeRequest, OfferedBook, UserLocation, UserProfile


def login(request):
    if request.user.is_authenticated:
        return redirect("home")

    login_form = EmailOrUsernameAuthenticationForm(request, data=request.POST or None)
    register_form = RegistrationForm()

    if request.method == "POST":
        if login_form.is_valid():
            user = login_form.get_user()
            auth_login(request, user)
            next_url = request.GET.get("next", "home")
            return redirect(next_url)

    return render(
        request,
        "login.html",
        {
            "login_form": login_form,
            "register_form": register_form,
        },
    )


def register(request):
    """
    Handle user registration.

    Creates an inactive user and sends an email verification link.
    The user must click the verification link to activate their account.
    """
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
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
            verification_path = reverse(
                "verify_email", kwargs={"uidb64": uid, "token": token}
            )
            verification_url = request.build_absolute_uri(verification_path)

            # Send verification email
            send_templated_email(
                to_email=user.email,
                subject="Verificá tu cuenta en CambioLibros",
                template_name="emails/verification_email",
                context={
                    "username": user.username,
                    "verification_url": verification_url,
                },
            )

            # Show confirmation page
            return render(
                request,
                "registration_confirmation.html",
                {
                    "email": user.email,
                },
            )
        else:
            # If form is invalid, re-render login page with errors
            login_form = EmailOrUsernameAuthenticationForm(request)
            return render(
                request,
                "login.html",
                {
                    "login_form": login_form,
                    "register_form": form,
                },
            )

    return redirect("login")


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
        return redirect("home")
    else:
        # Invalid or expired token
        return render(request, "verification_failed.html")


def logout(request):
    auth_logout(request)
    return redirect("login")


@login_required
def home(request):
    # Redirect to profile completion if user hasn't set up their profile
    if not hasattr(request.user, "profile"):
        return redirect("profile_edit")

    # Get books available in user's locations with already_requested annotation
    offered_books = OfferedBook.objects.for_user(request.user)

    return render(
        request,
        "home.html",
        {
            "offered_books": offered_books,
            "user": request.user,
        },
    )


@login_required
def profile_edit(request):
    """
    Create or edit user profile.
    """
    # Get existing profile if it exists
    try:
        profile = request.user.profile
        is_new_profile = False
    except UserProfile.DoesNotExist:
        profile = None
        is_new_profile = True

    if request.method == "POST":
        form = ProfileForm(request.POST)
        if form.is_valid():
            # Update User.first_name
            request.user.first_name = form.cleaned_data["first_name"]
            request.user.save()

            # Create or update UserProfile
            if profile:
                profile.contact_email = form.cleaned_data["email"]
                profile.alternate_contact = form.cleaned_data["alternate_contact"]
                profile.about = form.cleaned_data["about"]
                profile.save()
            else:
                profile = UserProfile.objects.create(
                    user=request.user,
                    contact_email=form.cleaned_data["email"],
                    alternate_contact=form.cleaned_data["alternate_contact"],
                    about=form.cleaned_data["about"],
                )

            # Update UserLocation entries
            # Delete existing locations
            UserLocation.objects.filter(user=request.user).delete()
            # Create new locations
            for area in form.cleaned_data["locations"]:
                UserLocation.objects.create(user=request.user, area=area)

            # Redirect based on whether this is first-time setup or edit
            if is_new_profile:
                return redirect("my_books")
            else:
                return redirect("profile", username=request.user.username)
    else:
        # Pre-populate form with existing data
        initial = {}
        if profile:
            initial = {
                "first_name": request.user.first_name,
                "email": profile.contact_email,
                "alternate_contact": profile.alternate_contact,
                "about": profile.about,
                "locations": [loc.area for loc in request.user.locations.all()],
            }
        else:
            # Default email to registration email
            initial = {
                "email": request.user.email,
            }
        form = ProfileForm(initial=initial)

    return render(request, "profile_edit.html", {"form": form})


@login_required
def profile(request, username):
    """
    View user profile.
    """
    from django.shortcuts import get_object_or_404

    profile_user = get_object_or_404(User, username=username)
    is_own_profile = request.user == profile_user

    # Get offered books (handles reuqests annotation if another user)
    offered_books = OfferedBook.objects.for_profile(profile_user, request.user)
    wanted_books = profile_user.wanted.all()

    sent_requests = None
    received_requests = None
    if is_own_profile:
        sent_requests = ExchangeRequest.objects.recent_sent_by(profile_user)
        received_requests = ExchangeRequest.objects.recent_received_by(profile_user)

    return render(
        request,
        "profile.html",
        {
            "profile_user": profile_user,
            "is_own_profile": is_own_profile,
            "offered_books": offered_books,
            "wanted_books": wanted_books,
            "sent_requests": sent_requests,
            "received_requests": received_requests,
        },
    )


@login_required
def my_books(request):
    """
    Manage user's offered books (bulk add/edit/delete).
    """
    # Create formset factory for user's offered books
    OfferedBookFormSet = modelformset_factory(
        OfferedBook,
        form=OfferedBookForm,
        extra=1,  # Always show 1 empty form for adding new books
        can_delete=True,
    )

    # Get queryset of user's books
    queryset = OfferedBook.objects.filter(user=request.user).order_by("created_at")

    if request.method == "POST":
        formset = OfferedBookFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            instances = formset.save(commit=False)

            # Assign user to new books
            for instance in instances:
                if not instance.pk:  # New book
                    instance.user = request.user
                instance.save()

            # Handle deletions
            for obj in formset.deleted_objects:
                obj.delete()

            return redirect("profile", username=request.user.username)
    else:
        formset = OfferedBookFormSet(queryset=queryset)

    return render(
        request,
        "my_books.html",
        {
            "formset": formset,
        },
    )


def send_templated_email(to_email, subject, template_name, context=None):
    """
    Send multipart email with HTML and plain text versions.

    template_name should be the base path without extension (e.g., "emails/welcome").
    Both .txt and .html versions will be rendered and sent.
    """
    if context is None:
        context = {}

    if isinstance(to_email, str):
        to_email = [to_email]

    text_message = render_to_string(f"{template_name}.txt", context)
    html_message = render_to_string(f"{template_name}.html", context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to_email,
    )
    email.attach_alternative(html_message, "text/html")

    return email.send(fail_silently=False)
