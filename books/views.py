import logging

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db import transaction
from django.forms import modelformset_factory
from django.http import JsonResponse
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
    WantedBookForm,
)
from books.models import (
    ExchangeRequest,
    OfferedBook,
    UserLocation,
    UserProfile,
    WantedBook,
)

logger = logging.getLogger(__name__)


def login(request):
    if request.user.is_authenticated:
        return redirect("home")

    login_form = EmailOrUsernameAuthenticationForm(request, data=request.POST or None)

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
            "registration_enabled": settings.REGISTRATION_ENABLED,
        },
    )


def register(request):
    """
    Handle user registration.

    Creates an inactive user and sends an email verification link.
    The user must click the verification link to activate their account.
    """
    if not settings.REGISTRATION_ENABLED:
        return redirect("login")

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
            _send_templated_email(
                to_email=user.email,
                subject="Verificá tu cuenta en GiraLibros",
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
        form = RegistrationForm()

    return render(request, "register.html", {"form": form})


def verify_email(request, uidb64, token):
    """
    Verify user's email address using the token sent via email.
    On success, activate the user and log them in.
    """
    if not settings.REGISTRATION_ENABLED:
        return redirect("login")

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
    if settings.REGISTRATION_ENABLED:
        return redirect("register")
    return redirect("login")


@login_required
def list_books(request):
    """
    List books with pagination support for infinite scroll.

    Handles both regular page loads and AJAX requests for pagination.
    AJAX requests (detected via X-Requested-With header) return JSON
    with HTML fragment and pagination metadata.
    """

    # Redirect to profile completion if user hasn't set up their profile
    if not hasattr(request.user, "profile"):
        return redirect("profile_edit")

    # Check filters (mutually exclusive)
    filter_wanted = "wanted" in request.GET
    search_query = request.GET.get("search", "").strip()

    # Get books available in user's locations with already_requested annotation
    offered_books = OfferedBook.objects.for_user(request.user)

    # Apply search filter if query is present
    if search_query:
        offered_books = OfferedBook.objects.search(offered_books, search_query)
    # Apply wanted books filter if requested
    elif filter_wanted:
        offered_books = OfferedBook.objects.filter_by_wanted(
            offered_books, request.user
        )

    # Paginate results
    page_size = getattr(settings, "BOOKS_PER_PAGE", 20)
    paginator = Paginator(offered_books, page_size)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Handle AJAX requests for infinite scroll
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if is_ajax:
        html = render_to_string(
            "_book_list.html",
            {
                "offered_books": page_obj,
                "user": request.user,
            },
            request=request,
        )
        return JsonResponse(
            {
                "html": html,
                "has_next": page_obj.has_next(),
                "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
            }
        )

    # Regular page load
    return render(
        request,
        "home.html",
        {
            "offered_books": page_obj,
            "user": request.user,
            "filter_wanted": filter_wanted,
            "search_query": search_query,
            "has_next": page_obj.has_next(),
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
                return redirect("my_offered")
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
def my_offered_books(request):
    """Manage user's offered books (bulk add/edit/delete)."""
    return _manage_books(
        request,
        book_model=OfferedBook,
        book_form=OfferedBookForm,
        template_name="my_offered_books.html",
    )


@login_required
def my_wanted_books(request):
    """Manage user's wanted books (bulk add/edit/delete)."""
    return _manage_books(
        request,
        book_model=WantedBook,
        book_form=WantedBookForm,
        template_name="my_wanted_books.html",
    )


@login_required
def request_exchange(request, book_id):
    """
    Create an exchange request for a book. Sends email notification to book owner.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    from datetime import timedelta

    from django.utils import timezone

    # Get the book
    try:
        book = OfferedBook.objects.select_related("user").get(pk=book_id)
    except OfferedBook.DoesNotExist:
        return JsonResponse({"error": "Libro no encontrado"}, status=404)

    # Check if user is trying to request their own book
    if book.user == request.user:
        return JsonResponse(
            {"error": "No podés solicitar tus propios libros"}, status=400
        )

    # Check if user has any offered books
    if not request.user.offered.exists():
        my_books_url = reverse("my_offered")
        return JsonResponse(
            {
                "error": f'Antes de enviar una solitud tenés que <a href="{my_books_url}">agregar tus libros ofrecidos</a>.'
            },
            status=400,
        )

    # Check if user already requested this book recently
    cutoff_date = timezone.now() - timedelta(days=settings.EXCHANGE_REQUEST_EXPIRY_DAYS)

    existing_request = ExchangeRequest.objects.filter(
        from_user=request.user, offered_book=book, created_at__gte=cutoff_date
    ).first()

    if existing_request:
        return JsonResponse(
            {"error": "Ya solicitaste este libro recientemente"}, status=400
        )

    # Check daily request limit
    last_24h = timezone.now() - timedelta(hours=24)

    requests_today = ExchangeRequest.objects.filter(
        from_user=request.user, created_at__gte=last_24h
    ).count()

    if requests_today >= settings.EXCHANGE_REQUEST_DAILY_LIMIT:
        return JsonResponse(
            {"error": "Llegaste al límite de pedidos por hoy, probá de nuevo mañana."},
            status=429,
        )

    # Create exchange request and send email atomically
    try:
        with transaction.atomic():
            exchange_request = ExchangeRequest.objects.create(
                from_user=request.user,
                to_user=book.user,
                offered_book=book,
                book_title=book.title,
                book_author=book.author,
            )

            # Build absolute URL for requester's profile
            profile_path = reverse(
                "profile", kwargs={"username": request.user.username}
            )
            requester_profile_url = request.build_absolute_uri(profile_path)

            _send_templated_email(
                to_email=book.user.profile.contact_email,
                subject="📚🔄📚 ¡Tenés una solicitud en GiraLibros.com!",
                template_name="emails/exchange_request",
                context={
                    "requester": request.user,
                    "book": book,
                    "exchange_request": exchange_request,
                    "requester_profile_url": requester_profile_url,
                },
            )
    except Exception:
        # If email fails, transaction is rolled back automatically
        logger.exception(
            f"Failed to send exchange request email for book {book_id} to user {book.user.id}"
        )
        return JsonResponse(
            {"error": "Hubo un error al procesar tu solicitud, probá más tarde."},
            status=500,
        )

    return JsonResponse(
        {
            "message": f"Le enviamos tu solicitud de intercambio a <b>{book.user.username}</b>.<br/>Te va a contactar si le interesa alguno de tus libros."
        },
        status=201,
    )


def _manage_books(request, book_model, book_form, template_name):
    """
    Generic view for managing user's books (offered or wanted).

    Handles bulk add/edit/delete operations via formsets.
    """
    BookFormSet = modelformset_factory(
        book_model,
        form=book_form,
        extra=1,
        can_delete=True,
    )

    queryset = book_model.objects.filter(user=request.user).order_by("created_at")

    if request.method == "POST":
        formset = BookFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            instances = formset.save(commit=False)

            for instance in instances:
                if not instance.pk:
                    instance.user = request.user
                instance.save()

            for obj in formset.deleted_objects:
                obj.delete()

            return redirect("profile", username=request.user.username)
    else:
        formset = BookFormSet(queryset=queryset)

    return render(request, template_name, {"formset": formset})


def _send_templated_email(to_email, subject, template_name, context=None):
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
