from django.contrib.auth.models import User
from django.shortcuts import render

from books.models import LocationArea, OfferedBook, UserLocation


class MockUser(User):
    """Mock user that allows setting locations without DB interaction"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mock_locations = []

    @property
    def locations(self):
        class MockLocationManager:
            def __init__(self, locations):
                self._locations = locations

            def all(self):
                return self._locations

        return MockLocationManager(self.mock_locations)


def home(request):
    # Create mock logged in user (not saved to DB)
    logged_user = MockUser(id=1, username="testuser", email="test@example.com")

    # Create mock UserLocation instances for the logged user
    user_locations = [
        UserLocation(user=logged_user, area=LocationArea.CABA),
        UserLocation(user=logged_user, area=LocationArea.GBA_NORTE),
    ]

    # Create mock User objects for book owners with their locations
    user1 = MockUser(id=2, username="juanperez")
    user1.mock_locations = [
        UserLocation(user=user1, area=LocationArea.CABA),
    ]

    user2 = MockUser(id=3, username="mariagomez")
    user2.mock_locations = [
        UserLocation(user=user2, area=LocationArea.GBA_NORTE),
        UserLocation(user=user2, area=LocationArea.GBA_SUR),
    ]

    user3 = MockUser(id=4, username="carloslopez")
    user3.mock_locations = [
        UserLocation(user=user3, area=LocationArea.CABA),
        UserLocation(user=user3, area=LocationArea.GBA_OESTE),
    ]

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
        OfferedBook(
            title="Ficciones",
            author="Jorge Luis Borges",
            user=user1,
            notes="Primera edición, excelente estado",
        ),
        OfferedBook(
            title="La casa de los espíritus",
            author="Isabel Allende",
            user=user2,
            notes="",
        ),
        OfferedBook(
            title="El Aleph",
            author="Jorge Luis Borges",
            user=user3,
            notes="Algunas páginas subrayadas",
        ),
        OfferedBook(
            title="Crónica de una muerte anunciada",
            author="Gabriel García Márquez",
            user=user1,
            notes="",
        ),
        OfferedBook(
            title="La tregua",
            author="Mario Benedetti",
            user=user2,
            notes="Muy buen estado",
        ),
        OfferedBook(
            title="Pedro Páramo",
            author="Juan Rulfo",
            user=user3,
            notes="Edición de bolsillo",
        ),
    ]

    return render(request, "home.html", {
        "offered_books": offered_books,
        "user": logged_user,
        "user_locations": user_locations,
    })
