import logging
from io import BytesIO

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetConfirmView, PasswordResetView
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from honeypot.decorators import check_honeypot
from PIL import Image, ImageOps

from books.forms import (
    CustomSetPasswordForm,
    EmailOrUsernameAuthenticationForm,
    OfferedBookForm,
    PasswordResetRequestForm,
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


def honeypot_responder(request, context):
    """
    Custom responder for honeypot violations.
    Logs the attempt and returns 403 Forbidden for easier monitoring.
    """
    logger.warning(
        f"Honeypot violation detected: IP={request.META.get('REMOTE_ADDR')}, "
        f"Path={request.path}, User-Agent={request.META.get('HTTP_USER_AGENT', 'N/A')}"
    )
    return HttpResponse("Forbidden", status=403)


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


@check_honeypot
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


class CustomPasswordResetView(PasswordResetView):
    """
    Password reset request using Django's built-in view.
    Configured to use our existing templates and email system.
    """

    template_name = "password_reset_request.html"
    form_class = PasswordResetRequestForm
    email_template_name = "emails/password_reset.txt"
    html_email_template_name = "emails/password_reset.html"
    success_url = reverse_lazy("password_reset_done")
    from_email = settings.DEFAULT_FROM_EMAIL


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """
    Password reset confirmation using Django's built-in view.
    Configured to use our existing templates and Bulma-styled form.
    """

    template_name = "password_reset_confirm.html"
    form_class = CustomSetPasswordForm
    success_url = reverse_lazy("password_reset_complete")


def password_reset_done(request):
    """Show confirmation that password reset email was sent."""
    return render(request, "password_reset_sent.html")


def password_reset_complete(request):
    """Show confirmation that password was successfully reset."""
    return render(request, "password_reset_complete.html")


def logout(request):
    auth_logout(request)
    return redirect("login")


@login_required
def about(request):
    """Display about page with site statistics."""
    from datetime import timedelta

    # Calculate statistics
    registered_users = User.objects.filter(profile__isnull=False).count()
    offered_books = OfferedBook.objects.available().count()

    # Requests in the last week
    one_week_ago = timezone.now() - timedelta(days=7)
    recent_requests = ExchangeRequest.objects.filter(
        created_at__gte=one_week_ago
    ).count()

    return render(
        request,
        "about.html",
        {
            "registered_users": registered_users,
            "offered_books": offered_books,
            "recent_requests": recent_requests,
        },
    )


def list_books(request):
    """
    List books with pagination support for infinite scroll.

    Handles both regular page loads and AJAX requests for pagination.
    AJAX requests (detected via X-Requested-With header) return JSON
    with HTML fragment and pagination metadata.
    """

    # Redirect to profile completion if authenticated user hasn't set up their profile
    if request.user.is_authenticated and not hasattr(request.user, "profile"):
        return redirect("profile_edit")

    # Parse query params
    search_query = request.GET.get("search", "").strip()
    wanted = "wanted" in request.GET
    photo = "photo" in request.GET
    my_locations = "my_locations" in request.GET

    # Get books with all filters applied
    offered_books = OfferedBook.objects.for_user(
        request.user,
        search=search_query or None,
        wanted=wanted,
        photo=photo,
        my_locations=my_locations,
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
                "next_page": page_obj.next_page_number()
                if page_obj.has_next()
                else None,
            }
        )

    # Regular page load
    return render(
        request,
        "home.html",
        {
            "offered_books": page_obj,
            "user": request.user,
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
                return redirect("home")
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
            # Default email to registration email and first_name to capitalized username
            initial = {
                "first_name": request.user.username.capitalize(),
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
    traded_books = None
    if is_own_profile:
        sent_requests = ExchangeRequest.objects.recent_sent_by(profile_user)
        received_requests = ExchangeRequest.objects.recent_received_by(profile_user)
        traded_books = OfferedBook.objects.traded_by(profile_user)

    return render(
        request,
        "profile.html",
        {
            "profile_user": profile_user,
            "is_own_profile": is_own_profile,
            "offered_books": offered_books,
            "wanted_books": wanted_books,
            "traded_books": traded_books,
            "sent_requests": sent_requests,
            "received_requests": received_requests,
            "books_per_page": settings.BOOKS_PER_PAGE,
        },
    )


@login_required
def my_offered_books(request, book_id=None):
    """Display form to add/edit offered books and list of existing books."""
    # Determine if editing or creating
    book = get_object_or_404(OfferedBook, id=book_id, user=request.user) if book_id else None

    if request.method == "POST":
        form = OfferedBookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            book = form.save(commit=False)
            if not book.user_id:
                book.user = request.user

            # Process cover image if uploaded
            if "cover_image" in request.FILES:
                try:
                    processed_image = _process_book_cover_image(request.FILES["cover_image"])
                    book.cover_image.save(processed_image.name, processed_image, save=False)
                    book.cover_uploaded_at = timezone.now()
                except ValueError as e:
                    form.add_error("cover_image", str(e))

            # Only save if no errors were added during processing
            if not form.errors:
                book.save()
                return redirect("my_offered")
    else:
        # GET request
        form = OfferedBookForm(instance=book)

    # Render template (for both GET and POST with errors)
    return render(
        request,
        "my_offered_books.html",
        {
            "form": form,
            "offered_books": OfferedBook.objects.available().filter(user=request.user).order_by("-created_at"),
            "editing_book_id": book_id,
        },
    )


@login_required
def delete_offered_book(request, book_id):
    """Mark an offered book as deleted (AJAX endpoint)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    book = get_object_or_404(OfferedBook, id=book_id, user=request.user)
    book.delete()

    return JsonResponse({"success": True})


@login_required
def trade_offered_book(request, book_id):
    """Mark an offered book as traded (AJAX endpoint)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    book = get_object_or_404(OfferedBook, id=book_id, user=request.user)
    book.trade()

    return JsonResponse({"success": True})


@login_required
def reserve_offered_book(request, book_id):
    """Toggle reservation status of an offered book (AJAX endpoint)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    book = get_object_or_404(OfferedBook, id=book_id, user=request.user)
    book.reserve()

    return JsonResponse({"success": True})


@login_required
def my_wanted_books(request):
    """Display form to add wanted books and list of existing books."""
    if request.method == "POST":
        form = WantedBookForm(request.POST)
        if form.is_valid():
            book = form.save(commit=False)
            book.user = request.user
            book.save()
            return redirect("my_wanted")
    else:
        form = WantedBookForm()

    return render(
        request,
        "my_wanted_books.html",
        {
            "form": form,
            "wanted_books": WantedBook.objects.filter(user=request.user).order_by("-created_at"),
        },
    )


@login_required
def delete_wanted_book(request, book_id):
    """Delete a wanted book (AJAX endpoint)."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    book = get_object_or_404(WantedBook, id=book_id, user=request.user)
    book.delete()

    return JsonResponse({"success": True})


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
        book = OfferedBook.objects.available().select_related("user").get(pk=book_id)
    except OfferedBook.DoesNotExist:
        return JsonResponse({"error": "Libro no encontrado"}, status=404)

    # Check if user is trying to request their own book
    if book.user == request.user:
        return JsonResponse(
            {"error": "No podés solicitar tus propios libros"}, status=400
        )

    # Check if user has any offered books
    if not request.user.offered.available().exists():
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
                subject="📚 ¡Tenés una solicitud en GiraLibros.com!",
                template_name="emails/exchange_request",
                context={
                    "requester": request.user,
                    "book": book,
                    "exchange_request": exchange_request,
                    "requester_profile_url": requester_profile_url,
                },
                reply_to=request.user.profile.contact_email,
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


@login_required
def upload_book_photo(request, book_id):
    """
    Handle book cover photo upload with thumbnail generation.
    """
    # Get the book and verify ownership
    book = get_object_or_404(OfferedBook, id=book_id, user=request.user)

    if request.method == "POST":
        # Validate file was uploaded
        if "cover_image" not in request.FILES:
            return HttpResponseBadRequest("No image file provided")

        uploaded_file = request.FILES["cover_image"]

        try:
            # Validate and process the uploaded image
            thumbnail = _process_book_cover_image(uploaded_file)

            # Save to model
            book.cover_image.save(thumbnail.name, thumbnail, save=False)
            book.cover_uploaded_at = timezone.now()
            book.save()

            # Return JSON response for AJAX request
            return JsonResponse({"success": True, "image_url": book.cover_image.url})

        except ValueError as e:
            return HttpResponseBadRequest(str(e))
        except Exception as e:
            logger.error(f"Error processing image upload: {e}")
            return HttpResponseBadRequest("Error processing image")

    return HttpResponseBadRequest("Method not allowed")


def _process_book_cover_image(uploaded_file):
    """
    Validate and process uploaded book cover image.
    Returns InMemoryUploadedFile ready to save, or raises ValueError on validation errors.
    """
    # Validate file size
    max_size = settings.BOOK_COVER_MAX_SIZE
    if uploaded_file.size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        raise ValueError(f"Image file too large (max {max_size_mb:.0f}MB)")

    # Validate file type
    allowed_types = settings.BOOK_COVER_ALLOWED_TYPES
    if uploaded_file.content_type not in allowed_types:
        raise ValueError("Invalid image format")

    # Open and process image with Pillow
    try:
        image = Image.open(uploaded_file)
    except Exception as e:
        logger.warning(f"PIL cannot identify image file: {uploaded_file.name} - {e}")
        raise ValueError("The uploaded file is not a valid image or is corrupt")

    # Apply EXIF orientation (fixes rotated mobile photos)
    # exif_transpose returns None if no transposing is needed
    image = ImageOps.exif_transpose(image) or image

    # Convert to RGB if necessary (handles PNG with transparency, etc.)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    # Center crop to book aspect ratio (2:3 - typical paperback)
    # This removes surroundings and focuses on the book
    target_aspect = 2 / 3  # width / height
    img_width, img_height = image.size
    img_aspect = img_width / img_height

    if img_aspect > target_aspect:
        # Image is too wide, crop sides
        new_width = int(img_height * target_aspect)
        left = (img_width - new_width) // 2
        image = image.crop((left, 0, left + new_width, img_height))
    else:
        # Image is too tall, crop top/bottom
        new_height = int(img_width / target_aspect)
        top = (img_height - new_height) // 2
        image = image.crop((0, top, img_width, top + new_height))

    # Calculate thumbnail size maintaining aspect ratio
    max_width = settings.BOOK_COVER_THUMBNAIL_MAX_WIDTH
    max_height = settings.BOOK_COVER_THUMBNAIL_MAX_HEIGHT
    image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

    # Save to BytesIO with optimization
    output = BytesIO()
    quality = settings.BOOK_COVER_JPEG_QUALITY
    image.save(output, format="JPEG", quality=quality, optimize=True)
    output.seek(0)

    # Create new InMemoryUploadedFile
    thumbnail = InMemoryUploadedFile(
        output,
        "ImageField",
        f"{uploaded_file.name.split('.')[0]}_thumb.jpg",
        "image/jpeg",
        output.getbuffer().nbytes,
        None,
    )

    return thumbnail


def _send_templated_email(
    to_email, subject, template_name, context=None, reply_to=None
):
    """
    Send multipart email with HTML and plain text versions.

    template_name should be the base path without extension (e.g., "emails/welcome").
    Both .txt and .html versions will be rendered and sent.
    """
    if context is None:
        context = {}

    if isinstance(to_email, str):
        to_email = [to_email]

    if isinstance(reply_to, str):
        reply_to = [reply_to]

    text_message = render_to_string(f"{template_name}.txt", context)
    html_message = render_to_string(f"{template_name}.html", context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to_email,
        reply_to=reply_to,
    )
    email.attach_alternative(html_message, "text/html")

    return email.send(fail_silently=False)
