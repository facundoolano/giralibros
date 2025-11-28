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

    class Meta:
        abstract = True  # This is the key!


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
        from django.db.models import Exists, OuterRef

        user_areas = user.locations.values_list("area", flat=True)

        return (
            self.filter(user__locations__area__in=user_areas)
            .exclude(user=user)
            .annotate(
                already_requested=Exists(
                    ExchangeRequest.objects.filter(
                        from_user=user,
                        to_user=OuterRef("user"),
                        book_title=OuterRef("title"),
                        book_author=OuterRef("author"),
                    )
                )
            )
            .select_related("user")
            .prefetch_related("user__locations")
            .distinct()
            .order_by("-created_at")
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


class WantedBook(BaseBook):
    "A book a user is interested in."

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wanted")


class ExchangeRequest(models.Model):
    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_requests"
    )
    # denormalized fields to accomodate changes/deletions of the target book
    to_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="received_requests", null=True
    )
    book_title = models.CharField(max_length=200)
    book_author = models.CharField(max_length=200)

    created_at = models.DateTimeField(auto_now_add=True)
