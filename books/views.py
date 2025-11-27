from django.contrib.auth.models import User
from django.shortcuts import render

from .models import OfferedBook


def home(request):
    # Create mock User objects (not saved to DB)
    user1 = User(username="juanperez")
    user2 = User(username="mariagomez")
    user3 = User(username="carloslopez")

    # Create mock OfferedBook instances (not saved to DB)
    offered_books = [
        OfferedBook(
            title="Cien años de soledad",
            author="Gabriel García Márquez",
            user=user1,
            notes="Buen estado, tapa blanda",
        ),
        OfferedBook(
            title="Rayuela",
            author="Julio Cortázar",
            user=user2,
            notes="Como nuevo",
        ),
        OfferedBook(
            title="El túnel",
            author="Ernesto Sábato",
            user=user3,
            notes="",
        ),
    ] * 10

    return render(request, "home.html", {"offered_books": offered_books})
