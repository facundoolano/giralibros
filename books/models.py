from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    # user.username
    # user.email

    contact_email = models.EmailField()
    alternate_contact = models.CharField(blank=True)

    about = models.TextField(blank=True)


class Area(models.TextChoices):
    CABA = "CABA", "CABA"
    GBA_NORTE = "GBA_NORTE", "GBA Norte"
    GBA_OESTE = "GBA_OESTE", "GBA Oeste"
    GBA_SUR = "GBA_SUR", "GBA Sur"


class UserLocation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="locations")
    area = models.CharField(max_length=20, choices=Area.choices)

    constraints = [
        models.UniqueConstraint(fields=["user", "area"], name="unique_user_area")
    ]

    def __str__(self):
        return f"{self.user.username} - {self.get_area_display()}"


# abstract
class BaseBook(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=200)

    class Meta:
        abstract = True  # This is the key!


class OfferedBook(BaseBook):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="offered")
    notes = models.TextField()
    reserved = models.BooleanField(default=False)


class WantedBook(BaseBook):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wanted")
