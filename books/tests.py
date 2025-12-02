from unittest.mock import patch

from django.core import mail
from django.test import Client, override_settings
from django.test import TestCase as DjangoTestCase
from django.urls import reverse


class BaseTestCase(DjangoTestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()

    def register_and_verify_user(
        self,
        username="testuser",
        email="test@example.com",
        password="testpass123",
        fill_profile=False,
    ):
        """
        Register a new user and verify their email.
        Returns after verification (user will be logged in).
        Use this helper in tests that need a user to exist but aren't testing registration itself.

        If fill_profile=True, also fills in the profile with basic info using the email username as first_name.
        """
        response = self.client.post(
            reverse("register"),
            {
                "username": username,
                "email": email,
                "password": password,
            },
        )
        verify_url = self.get_verification_url_from_email(email)
        self.client.get(verify_url)

        if fill_profile:
            # Extract first name from email (part before @)
            first_name = email.split("@")[0]
            self.client.post(
                reverse("profile_edit"),
                {
                    "first_name": first_name,
                    "email": email,
                    "locations": ["CABA_CENTRO"],
                },
            )

        return response

    def get_verification_url_from_email(self, email):
        """
        Extract verification URL from email sent during registration.
        """
        # Find the email sent to this address
        sent_email = None
        for email_msg in mail.outbox:
            if email in email_msg.to:
                sent_email = email_msg
                break

        if not sent_email:
            raise AssertionError(f"No email found for {email}")

        # Extract the verification URL from the email body
        # The URL is in the format: http://testserver/verify/{uidb64}/{token}/
        email_body = sent_email.body
        lines = email_body.split("\n")
        for line in lines:
            if "/verify/" in line:
                return line.strip()

        raise AssertionError("No verification URL found in email body")


# Create your tests here.
class UserTest(BaseTestCase):
    def test_login_register(self):
        """Test that users must register and verify email before logging in."""
        # Test login with nonexistent user fails
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Por favor introduzca un nombre de usuario"
        )  # Login error message

        # Register user with same credentials
        response = self.client.post(
            reverse("register"),
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "test@example.com"
        )  # Registration confirmation page

        # Extract verification URL from email
        verify_url = self.get_verification_url_from_email("test@example.com")

        # Follow verification link
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, 302)  # Redirects after verification

        # Try login and it should work
        response = self.client.post(
            reverse("login"),
            {"username": "testuser", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 302)  # Redirects after successful login

    def test_login_no_verified_fails(self):
        """Test that unverified users cannot log in until they verify their email."""
        # Register user without verifying
        response = self.client.post(
            reverse("register"),
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)

        # Try login, should fail
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)  # Stays on login page
        self.assertContains(
            response, "Por favor introduzca un nombre de usuario"
        )  # Login error message

        # Verify email
        verify_url = self.get_verification_url_from_email("test@example.com")
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, 302)  # Redirects after verification

        # Try login again, should succeed
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 302)  # Redirects after successful login

    def test_login_wrong_password(self):
        """Test that login fails with appropriate error message for wrong password."""
        self.register_and_verify_user()
        self.client.logout()

        # Try login with wrong password
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": "wrongpassword",
            },
        )
        self.assertEqual(response.status_code, 200)  # Stays on login page
        self.assertContains(
            response, "Por favor introduzca un nombre de usuario"
        )  # Error message

    def test_logout_redirects(self):
        """Test that logout redirects to login and clears authentication."""
        self.register_and_verify_user()

        # Logout should redirect to login
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))

        # Try to navigate to home, should redirect to login
        response = self.client.get(reverse("home"))
        self.assertRedirects(
            response, reverse("login") + "?next=/"
        )  # Login with next parameter

    def test_login_username(self):
        """Test that users can log in with either username or email."""
        self.register_and_verify_user()
        self.client.logout()

        # Login with username should succeed
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 302)  # Redirects after successful login

        # Logout
        self.client.logout()

        # Login with email should also succeed
        response = self.client.post(
            reverse("login"),
            {
                "username": "test@example.com",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 302)  # Redirects after successful login

    def test_register_fails_repeated_user(self):
        """Test that registration fails when username or email already exists."""
        # Register user without verifying
        response = self.client.post(
            reverse("register"),
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)

        # Try to register again with same username, should fail
        response = self.client.post(
            reverse("register"),
            {
                "username": "testuser",
                "email": "different@example.com",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)  # Stays on form
        self.assertContains(
            response, "Este usuario ya está registrado"
        )  # Error message

        # Try to register again with same email, should fail
        response = self.client.post(
            reverse("register"),
            {
                "username": "differentuser",
                "email": "test@example.com",
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)  # Stays on form
        self.assertContains(response, "Este email ya está registrado")  # Error message

    def test_home_redirects_on_no_profile(self):
        """Test that users without profile data are redirected to profile setup before accessing home."""
        self.register_and_verify_user()

        # Navigate to home, should redirect to edit profile (no profile exists yet)
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("profile_edit"))

        # Save minimum profile data
        response = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Test",
                "email": "test@example.com",
                "locations": ["CABA_CENTRO"],
            },
        )
        self.assertRedirects(
            response, reverse("my_offered")
        )  # First-time setup redirects to my_offered

        # Navigate to home, should now stay on home
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)  # Successfully loads home page

    def test_profile_view_profile_afer_edit(self):
        """Test profile viewing behavior after editing."""
        self.register_and_verify_user()

        # Save minimum profile data
        response = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Test",
                "email": "test@example.com",
                "locations": ["CABA_CENTRO"],
            },
        )
        self.assertRedirects(
            response, reverse("my_offered")
        )  # First-time setup redirects to my_offered

        # Navigate to edit profile explicitly, edit again
        response = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Updated Name",
                "email": "test@example.com",
                "locations": ["CABA_CENTRO", "GBA_NORTE"],
            },
        )
        # Subsequent edits should redirect to profile view
        self.assertRedirects(
            response, reverse("profile", kwargs={"username": "testuser"})
        )

    def test_profile_edit_validations(self):
        """Test that profile form validates required fields and data format."""
        # TODO human to specify
        pass

    def test_throttle_registration_attempts(self):
        """Test that repeated registration attempts are rate-limited."""
        # TODO human to specify
        pass


class BooksTest(BaseTestCase):
    def test_own_books_excluded(self):
        """Test that users do not see their own books in the book listing."""
        # Register first user with profile and books
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books([("Book A", "Author A"), ("Book B", "Author B")])
        self.client.logout()

        # Register second user with profile and books
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        self.add_books([("Book C", "Author C"), ("Book D", "Author D")])

        # User 2 should see only user 1's books (not their own)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Book A")
        self.assertContains(response, "Book B")
        self.assertNotContains(response, "Book C")
        self.assertNotContains(response, "Book D")

        self.client.logout()

        # Log in as user 1 and check they see only user 2's books
        self.client.post(
            reverse("login"),
            {
                "username": "user1",
                "password": "testpass123",
            },
        )
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Book A")
        self.assertNotContains(response, "Book B")
        self.assertContains(response, "Book C")
        self.assertContains(response, "Book D")

    def test_filter_by_location(self):
        """Test that book listings are filtered based on user's selected location areas."""
        # Register 4 users, each in a different location with one book
        locations = ["CABA_CENTRO", "GBA_NORTE", "GBA_OESTE", "GBA_SUR"]
        for i, location in enumerate(locations):
            username = f"user{i + 1}"
            email = f"user{i + 1}@example.com"
            self.register_and_verify_user(username=username, email=email)
            self.client.post(
                reverse("profile_edit"),
                {
                    "first_name": f"User {i + 1}",
                    "email": email,
                    "locations": [location],
                },
            )
            self.add_books([(f"Book {location}", f"Author {i + 1}")])
            self.client.logout()

        # Register user 5 with all areas - should see all books
        self.register_and_verify_user(username="user5", email="user5@example.com")
        self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "User Five",
                "email": "user5@example.com",
                "locations": ["CABA_CENTRO", "GBA_NORTE", "GBA_OESTE", "GBA_SUR"],
            },
        )

        response = self.client.get(reverse("home"))
        self.assertContains(response, "Book CABA_CENTRO")
        self.assertContains(response, "Book GBA_NORTE")
        self.assertContains(response, "Book GBA_OESTE")
        self.assertContains(response, "Book GBA_SUR")

        # Edit to only 2 areas - should see only those 2 books
        self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "User Five",
                "email": "user5@example.com",
                "locations": ["CABA_CENTRO", "GBA_NORTE"],
            },
        )

        response = self.client.get(reverse("home"))
        self.assertContains(response, "Book CABA_CENTRO")
        self.assertContains(response, "Book GBA_NORTE")
        self.assertNotContains(response, "Book GBA_OESTE")
        self.assertNotContains(response, "Book GBA_SUR")

    def test_text_search(self):
        """Test that text search filters books by normalized title and author with accent-insensitive matching."""
        # Register first user with 4 books (2 by same author)
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books([
            ("Rayuela", "Julio Cortázar"),
            ("Bestiario", "Julio Cortázar"),
            ("Ficciones", "Jorge Luis Borges"),
            ("El Aleph", "Jorge Luis Borges"),
        ])
        self.client.logout()

        # Register second user to make books searchable
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        self.add_books([("Book B", "Author B")])

        # Search by specific title - should find one book
        response = self.client.get(reverse("home"), {"search": "Rayuela"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rayuela")
        self.assertNotContains(response, "Bestiario")
        self.assertNotContains(response, "Ficciones")

        # Search by author - should find both books by that author
        response = self.client.get(reverse("home"), {"search": "Cortázar"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rayuela")
        self.assertContains(response, "Bestiario")
        self.assertNotContains(response, "Ficciones")

        # Search with accent variations - should still match
        response = self.client.get(reverse("home"), {"search": "cortazar"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rayuela")
        self.assertContains(response, "Bestiario")

        # Search by title + author - should find specific book
        response = self.client.get(reverse("home"), {"search": "Rayuela Cortázar"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rayuela")
        self.assertNotContains(response, "Bestiario")

        # Search with reversed order - should still work
        response = self.client.get(reverse("home"), {"search": "Cortázar Rayuela"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rayuela")
        self.assertNotContains(response, "Bestiario")

    def test_filter_by_wanted_books(self):
        """Test that wanted books filter shows only offered books matching user's wanted list."""
        # Register first user with several books
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books([
            ("Rayuela", "Julio Cortázar"),
            ("Ficciones", "Jorge Luis Borges"),
            ("El túnel", "Ernesto Sábato"),
            ("Cien años de soledad", "Gabriel García Márquez"),
        ])
        self.client.logout()

        # Register second user with wanted books
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        # Add offered book (needed to see other users' books)
        self.add_books([("Book B", "Author B")])
        # Add wanted books
        self.add_books([
            ("Rayuela", "Julio Cortázar"),
            ("Ficciones", "Jorge Luis Borges"),
        ], wanted=True)

        # Filter by wanted books - should only show matching books
        response = self.client.get(reverse("home"), {"wanted": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rayuela")
        self.assertContains(response, "Ficciones")
        self.assertNotContains(response, "El túnel")
        self.assertNotContains(response, "Cien años de soledad")

        # Should handle accent variations (wanted without accent matches offered with accent)
        self.add_books([("Cronica de una muerte anunciada", "Garcia Marquez")], wanted=True)
        response = self.client.get(reverse("home"), {"wanted": ""})
        # If user1 had this book with accents, it would match

    def test_request_book_exchange(self):
        """Test that exchange requests send email with contact details and requester's book list."""
        # Register first user with one book
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books([("Book A", "Author A")])
        self.client.logout()

        # Register second user with one book
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        self.add_books([("Book B", "Author B")])

        # Get book ID from home page context
        response = self.client.get(reverse("home"))
        offered_books = response.context["offered_books"]
        book = offered_books[0]

        # Clear email outbox and send exchange request
        mail.outbox = []
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": book.id})
        )
        self.assertEqual(response.status_code, 201)

        # Check that exactly one email was sent to the book owner
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("user1@example.com", sent_email.to)

        # Check email contains requester's contact details
        self.assertIn("user2@example.com", sent_email.body)
        self.assertIn("user2", sent_email.body)

        # Check email lists requester's offered books
        self.assertIn("Book B", sent_email.body)
        self.assertIn("Author B", sent_email.body)

    def test_request_book_reflected_in_profile(self):
        """Test that when a successful exchange request is sent, it shows up in both user's profiles."""
        # Register first user with one book
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books([("Book A", "Author A")])
        self.client.logout()

        # Register second user with one book
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        self.add_books([("Book B", "Author B")])

        # Get book ID from home page context
        response = self.client.get(reverse("home"))
        offered_books = response.context["offered_books"]
        book = offered_books[0]

        # Send exchange request
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": book.id})
        )
        self.assertEqual(response.status_code, 201)

        # Check user 2's profile shows outgoing request
        response = self.client.get(reverse("profile", kwargs={"username": "user2"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book A")  # The book they requested

        self.client.logout()

        # Log in as user 1 and check their profile shows incoming request
        self.client.post(
            reverse("login"),
            {
                "username": "user1",
                "password": "testpass123",
            },
        )
        response = self.client.get(reverse("profile", kwargs={"username": "user1"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book A")  # The book that was requested
        self.assertContains(response, "user2")  # The user who requested it

    def test_mark_as_already_requested(self):
        """Test that books already requested by a user are marked differently in the listing."""
        # Register first user with one book
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books([("Book A", "Author A")])
        self.client.logout()

        # Register second user with one book
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        self.add_books([("Book B", "Author B")])

        # Check home page shows book with exchange button
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book A")
        self.assertContains(response, "Cambio")

        # Get book ID and send exchange request
        offered_books = response.context["offered_books"]
        book = offered_books[0]
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": book.id})
        )
        self.assertEqual(response.status_code, 201)

        # Check home page now shows book as already requested
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book A")
        self.assertContains(response, "Ya solicitado")

    def test_fail_on_already_requested(self):
        """Test that users cannot request the same book twice."""
        # Register first user with one book
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books([("Book A", "Author A")])
        self.client.logout()

        # Register second user with one book
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        self.add_books([("Book B", "Author B")])

        # Get book ID from home page context
        response = self.client.get(reverse("home"))
        offered_books = response.context["offered_books"]
        book = offered_books[0]

        # Send first request, should succeed
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": book.id})
        )
        self.assertEqual(response.status_code, 201)

        # Send second request for same book, should fail
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": book.id})
        )
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn("error", response_data)

    def test_email_error_on_exchange_request(self):
        """Test handling of email sending failures during exchange requests."""
        # Register first user with one book
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books([("Book A", "Author A")])
        self.client.logout()

        # Register second user with one book
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        self.add_books([("Book B", "Author B")])

        # Get book ID from home page context
        response = self.client.get(reverse("home"))
        offered_books = response.context["offered_books"]
        book = offered_books[0]

        # Mock email sending to raise an exception
        with patch("django.core.mail.message.EmailMessage.send") as mock_send:
            mock_send.side_effect = Exception("Email service failed")

            # Send exchange request, should fail
            response = self.client.post(
                reverse("request_exchange", kwargs={"book_id": book.id})
            )
            self.assertEqual(response.status_code, 500)
            response_data = response.json()
            self.assertIn("error", response_data)

        # Verify request doesn't show up in user's profile
        response = self.client.get(reverse("profile", kwargs={"username": "user2"}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Book A")

    def test_error_on_request_with_no_offered(self):
        """Test that a user with no listed offered books cannot send an exchange request."""
        # Register first user with one book
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books([("Book A", "Author A")])
        self.client.logout()

        # Register second user with no books
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )

        # Get book ID from home page context
        response = self.client.get(reverse("home"))
        offered_books = response.context["offered_books"]
        book = offered_books[0]

        # Send exchange request, should fail
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": book.id})
        )
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn("error", response_data)
        self.assertIn("agregar tus libros", response_data["error"])

    @override_settings(EXCHANGE_REQUEST_DAILY_LIMIT=2)
    def test_error_on_request_throttled(self):
        """Test that an exchange request fails if the user has already exceeded their limit for the day."""
        # Register first user with 3 books
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books(
            [("Book A", "Author A"), ("Book B", "Author B"), ("Book C", "Author C")]
        )
        self.client.logout()

        # Register second user with one book
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        self.add_books([("Book D", "Author D")])

        # Get all three books from home page
        response = self.client.get(reverse("home"))
        offered_books = response.context["offered_books"]
        self.assertEqual(len(offered_books), 3)

        # First request should succeed
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": offered_books[0].id})
        )
        self.assertEqual(response.status_code, 201)

        # Second request should succeed
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": offered_books[1].id})
        )
        self.assertEqual(response.status_code, 201)

        # Third request should fail due to throttling
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": offered_books[2].id})
        )
        self.assertEqual(response.status_code, 429)
        response_data = response.json()
        self.assertIn("error", response_data)
        self.assertIn("límite de pedidos", response_data["error"])

    def test_wanted_book_reflected_in_profile(self):
        """Test that wanted books added by a user are displayed on their profile."""
        # Register and verify user with profile
        self.register_and_verify_user(
            username="testuser", email="test@example.com", fill_profile=True
        )

        # Add a couple of wanted books
        self.add_books(
            [("Cien años de soledad", "García Márquez"), ("1984", "George Orwell")],
            wanted=True,
        )

        # Check that wanted books show up in the user's profile
        response = self.client.get(reverse("profile", kwargs={"username": "testuser"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cien años de soledad")
        self.assertContains(response, "García Márquez")
        self.assertContains(response, "1984")
        self.assertContains(response, "George Orwell")

    def add_books(self, books, wanted=False):
        """
        Add books for the currently logged-in user.

        Args:
            books: List of (title, author) tuples
            wanted: If True, adds wanted books; otherwise adds offered books
        """
        form_data = {
            "form-TOTAL_FORMS": str(len(books)),
            "form-INITIAL_FORMS": "0",
        }
        for i, (title, author) in enumerate(books):
            form_data[f"form-{i}-title"] = title
            form_data[f"form-{i}-author"] = author

        url = reverse("my_wanted") if wanted else reverse("my_offered")
        self.client.post(url, form_data)


class BooksPaginationTest(BaseTestCase):
    def test_pagination_limits_results(self):
        """Test that book listing is paginated at 20 items per page."""
        # Register user1 with 25 books
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        books = [(f"Book {i}", f"Author {i}") for i in range(25)]
        self.add_books(books)
        self.client.logout()

        # Register user2 to view the books
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )

        # First page should show exactly 20 books
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        offered_books = response.context["offered_books"]
        self.assertEqual(len(offered_books), 20)

        # Should indicate more pages available
        self.assertTrue(response.context["has_next"])

        # Verify first page shows books 0-19 (most recent first)
        self.assertContains(response, "Book 24")  # Most recent
        self.assertContains(response, "Book 5")   # 20th book
        self.assertNotContains(response, "Book 4")  # Should be on page 2

    def test_pagination_second_page(self):
        """Test that second page shows remaining books."""
        # Register user1 with 25 books
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        books = [(f"Book {i}", f"Author {i}") for i in range(25)]
        self.add_books(books)
        self.client.logout()

        # Register user2 to view the books
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )

        # Second page should show remaining 5 books
        response = self.client.get(reverse("home"), {"page": 2})
        self.assertEqual(response.status_code, 200)
        offered_books = response.context["offered_books"]
        self.assertEqual(len(offered_books), 5)

        # Should indicate no more pages
        self.assertFalse(response.context["has_next"])

        # Verify second page shows books 0-4
        self.assertContains(response, "Book 4")
        self.assertContains(response, "Book 0")
        self.assertNotContains(response, "Book 5")  # Was on page 1

    def test_pagination_ajax_response(self):
        """Test that AJAX requests return JSON with HTML and pagination metadata."""
        # Setup: user1 with 25 books
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        books = [(f"Book {i}", f"Author {i}") for i in range(25)]
        self.add_books(books)
        self.client.logout()

        # user2 views page 2 via AJAX
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )

        response = self.client.get(
            reverse("home") + "?page=2",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        data = response.json()
        self.assertIn("html", data)
        self.assertIn("has_next", data)
        self.assertIn("next_page", data)

        # Page 2 should show remaining 5 books, no next page
        self.assertFalse(data["has_next"])
        self.assertIsNone(data["next_page"])

        # HTML should contain the book content
        self.assertIn("Book 4", data["html"])
        self.assertIn("Book 0", data["html"])

    def test_pagination_ajax_first_page(self):
        """Test that AJAX request for first page returns correct pagination metadata."""
        # Setup: user1 with 25 books
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        books = [(f"Book {i}", f"Author {i}") for i in range(25)]
        self.add_books(books)
        self.client.logout()

        # user2 views page 1 via AJAX
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )

        response = self.client.get(
            reverse("home") + "?page=1",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Page 1 should have 20 books and indicate next page
        self.assertTrue(data["has_next"])
        self.assertEqual(data["next_page"], 2)

    def test_pagination_with_search(self):
        """Test that pagination works correctly with search filters."""
        # Register user1 with 25 books by same author
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        books = [(f"Book {i}", "Julio Cortázar") for i in range(25)]
        self.add_books(books)
        self.client.logout()

        # Register user2 to search
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )

        # Search for author - should get paginated results
        response = self.client.get(reverse("home"), {"search": "Cortázar"})
        self.assertEqual(response.status_code, 200)
        offered_books = response.context["offered_books"]
        self.assertEqual(len(offered_books), 20)
        self.assertTrue(response.context["has_next"])

        # Second page of search results
        response = self.client.get(reverse("home"), {"search": "Cortázar", "page": 2})
        self.assertEqual(response.status_code, 200)
        offered_books = response.context["offered_books"]
        self.assertEqual(len(offered_books), 5)
        self.assertFalse(response.context["has_next"])

    def test_pagination_with_wanted_filter(self):
        """Test that pagination works correctly with wanted books filter."""
        # Register user1 with 25 books
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        books = [(f"Book {i}", f"Author {i}") for i in range(25)]
        self.add_books(books)
        self.client.logout()

        # Register user2 with all 25 books as wanted
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        self.add_books([("Dummy", "Dummy")])  # Need at least one offered book
        wanted_books = [(f"Book {i}", f"Author {i}") for i in range(25)]
        self.add_books(wanted_books, wanted=True)

        # Filter by wanted books - should get paginated results
        response = self.client.get(reverse("home"), {"wanted": ""})
        self.assertEqual(response.status_code, 200)
        offered_books = response.context["offered_books"]
        self.assertEqual(len(offered_books), 20)
        self.assertTrue(response.context["has_next"])

        # Second page of wanted filter
        response = self.client.get(reverse("home"), {"wanted": "", "page": 2})
        self.assertEqual(response.status_code, 200)
        offered_books = response.context["offered_books"]
        self.assertEqual(len(offered_books), 5)
        self.assertFalse(response.context["has_next"])

    def test_pagination_invalid_page(self):
        """Test that invalid page numbers are handled gracefully."""
        # Register user1 with 5 books
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        books = [(f"Book {i}", f"Author {i}") for i in range(5)]
        self.add_books(books)
        self.client.logout()

        # Register user2 to view the books
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )

        # Request page 999 - should return last page (Django's get_page behavior)
        response = self.client.get(reverse("home"), {"page": 999})
        self.assertEqual(response.status_code, 200)
        offered_books = response.context["offered_books"]
        self.assertEqual(len(offered_books), 5)
        self.assertFalse(response.context["has_next"])

        # Request page 0 - should return first page
        response = self.client.get(reverse("home"), {"page": 0})
        self.assertEqual(response.status_code, 200)
        offered_books = response.context["offered_books"]
        self.assertEqual(len(offered_books), 5)

    def add_books(self, books, wanted=False):
        """
        Add books for the currently logged-in user.

        Args:
            books: List of (title, author) tuples
            wanted: If True, adds wanted books; otherwise adds offered books
        """
        form_data = {
            "form-TOTAL_FORMS": str(len(books)),
            "form-INITIAL_FORMS": "0",
        }
        for i, (title, author) in enumerate(books):
            form_data[f"form-{i}-title"] = title
            form_data[f"form-{i}-author"] = author

        url = reverse("my_wanted") if wanted else reverse("my_offered")
        self.client.post(url, form_data)
