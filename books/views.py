from django.contrib.auth.models import User
from django.shortcuts import render

from books.models import OfferedBook


def home(request):
    # TODO: Replace with actual authenticated user (request.user)
    # For now, mock with testuser from fixtures
    mock_user = User.objects.get(username="testuser")

    # Get books available in user's locations with already_requested annotation
    offered_books = OfferedBook.objects.for_user(mock_user)

    return render(request, "home.html", {
        "offered_books": offered_books,
        "user": mock_user,
    })
