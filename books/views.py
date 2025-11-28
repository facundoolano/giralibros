from django.contrib.auth.models import User
from django.db.models import Value
from django.shortcuts import render

from books.models import OfferedBook


def home(request):
    # TODO: Replace with actual authenticated user (request.user)
    # For now, mock with testuser from fixtures
    mock_user = User.objects.get(username="testuser")

    # Load all offered books from the database
    # TODO: When authentication is implemented, use Exists() subquery to check
    # if current user has already requested each book (see OfferedBook model docstring)
    offered_books = OfferedBook.objects.annotate(
        already_requested=Value(False)
    )

    return render(request, "home.html", {
        "offered_books": offered_books,
        "user": mock_user,
    })
