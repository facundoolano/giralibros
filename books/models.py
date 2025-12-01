import re

from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    # user.username
    # user.email

    contact_email = models.EmailField(
        help_text="The email the user wants to share with others when sending an exchange request."
    )
    alternate_contact = models.CharField(
        blank=True,
        max_length=200,
        help_text="Some alternative means of contact for exchanging books, e.g. WhatsApp phone number.",
    )

    about = models.TextField(
        blank=True,
        help_text="Miscelaneous notes to be displayed on the user public profile and on exchange requests.",
    )


class LocationArea(models.TextChoices):
    CABA = "CABA", "CABA"
    GBA_NORTE = "GBA_NORTE", "GBA Norte"
    GBA_OESTE = "GBA_OESTE", "GBA Oeste"
    GBA_SUR = "GBA_SUR", "GBA Sur"


class UserLocation(models.Model):
    """
    Represent a region where users offer to make exchanges, which affects which other user's books
    are visible to them.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="locations")
    area = models.CharField(max_length=20, choices=LocationArea.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "area"], name="unique_user_area")
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_area_display()}"


# abstract
class BaseBook(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    title_normalized = models.CharField(max_length=200, db_index=True)
    author_normalized = models.CharField(max_length=200, db_index=True)

    def normalize_spanish(self, text):
        """Normalize text for search"""
        text = text.lower()
        replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u"}
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = text.replace("100", "cien")
        text = re.sub(r"[^\wñ\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def save(self, *args, **kwargs):
        # This runs for ALL child models
        self.title_normalized = self.normalize_spanish(self.title)
        self.author_normalized = self.normalize_spanish(self.author)
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class OfferedBookManager(models.Manager):
    def for_user(self, user):
        """
        Return books available in the user's locations, annotated with whether
        the user has already requested each book.

        This query:
        - Filters books by user's location areas
        - Excludes the user's own books
        - Annotates with 'already_requested' flag via Exists subquery
        - Optimizes with select_related and prefetch_related to avoid N+1 queries
        """
        user_areas = user.locations.values_list("area", flat=True)

        queryset = (
            self.filter(user__locations__area__in=user_areas)
            .exclude(user=user)
            .select_related("user")
            .prefetch_related("user__locations")
            .distinct()
            .order_by("-created_at")
        )

        return self._annotate_already_requested(queryset, user)

    def for_profile(self, profile_user, viewing_user):
        """
        Return books for a profile page.

        - If viewing own profile: returns all books without annotation
        - If viewing another user's profile: annotates with 'already_requested' flag
        """
        queryset = self.filter(user=profile_user)

        if viewing_user != profile_user:
            queryset = self._annotate_already_requested(queryset, viewing_user)

        return queryset

    def search(self, queryset, search_query):
        """
        Filter books by search query against normalized title and author fields.

        The search query is normalized using the same logic as book titles/authors,
        then split into words. Books match if all words appear in either the title
        or author (case-insensitive, accent-insensitive).
        """
        if not search_query:
            return queryset

        # Normalize the search query using the same method as books
        # We need to instantiate a temporary model to access the method
        temp_book = self.model()
        normalized_query = temp_book.normalize_spanish(search_query)

        # Split into individual words
        search_words = normalized_query.split()

        # Filter: all words must appear in title or author
        from django.db.models import Q

        for word in search_words:
            queryset = queryset.filter(
                Q(title_normalized__icontains=word) | Q(author_normalized__icontains=word)
            )

        return queryset

    def filter_by_wanted(self, queryset, user):
        """
        Filter offered books that match the user's wanted books.

        A book matches if both the normalized title and author from a wanted book
        appear as substrings in the offered book (case-insensitive, accent-insensitive).
        Results are aggregated across all wanted books and deduplicated.
        """
        from django.db.models import Q

        wanted_books = user.wanted.all()

        if not wanted_books.exists():
            return queryset.none()

        match_conditions = Q()

        for wanted in wanted_books:
            match_conditions |= (
                Q(title_normalized__icontains=wanted.title_normalized) &
                Q(author_normalized__icontains=wanted.author_normalized)
            )

        return queryset.filter(match_conditions).distinct()

    def _annotate_already_requested(self, queryset, requesting_user):
        """
        Helper to add already_requested annotation to a queryset.

        Checks if the user has a recent exchange request (within EXCHANGE_REQUEST_EXPIRY_DAYS)
        for each book. After the expiry period, requests can be retried.
        """
        from datetime import timedelta

        from django.conf import settings
        from django.db.models import Exists, OuterRef
        from django.utils import timezone

        expiry_days = getattr(settings, "EXCHANGE_REQUEST_EXPIRY_DAYS", 15)
        cutoff_date = timezone.now() - timedelta(days=expiry_days)

        return queryset.annotate(
            already_requested=Exists(
                ExchangeRequest.objects.filter(
                    from_user=requesting_user,
                    offered_book=OuterRef("pk"),
                    created_at__gte=cutoff_date,
                )
            )
        )


class OfferedBook(BaseBook):
    """A book a user offers for exchanging."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="offered")
    notes = models.TextField(blank=True)
    reserved = models.BooleanField(
        default=False,
        help_text="Used to mark that this book is reserved for a not yet fulfilled exchange.",
    )

    objects = OfferedBookManager()

    @property
    def cover_image(self) -> str:
        """
        Return a consistent book cover image filename based on book ID.
        Uses modulo to cycle through available book images.
        """
        # Number of available book images
        NUM_BOOK_IMAGES = 4
        image_num = ((self.id - 1) % NUM_BOOK_IMAGES) + 1
        return f"img/book{image_num}.webp"


class WantedBook(BaseBook):
    "A book a user is interested in."

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wanted")


class ExchangeRequestManager(models.Manager):
    def recent_sent_by(self, user, limit=10):
        """
        Return recent exchange requests sent by a user.
        Ordered by most recent first, limited to specified count.
        """
        return (
            self.filter(from_user=user)
            .select_related("to_user")
            .order_by("-created_at")[:limit]
        )

    def recent_received_by(self, user, limit=10):
        """
        Return recent exchange requests received by a user.
        Ordered by most recent first, limited to specified count.
        """
        return (
            self.filter(to_user=user)
            .select_related("from_user")
            .order_by("-created_at")[:limit]
        )


class ExchangeRequest(models.Model):
    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_requests"
    )
    to_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="received_requests", null=True
    )
    # Reference to the actual book, set to null if book is deleted
    offered_book = models.ForeignKey(
        OfferedBook, on_delete=models.SET_NULL, null=True, related_name="requests"
    )
    # Denormalized fields to preserve request details when book is deleted or edited
    book_title = models.CharField(max_length=200)
    book_author = models.CharField(max_length=200)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = ExchangeRequestManager()
