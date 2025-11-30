from django.contrib.auth.models import User
from django.core import mail
from django.test import Client
from django.test import TestCase as DjangoTestCase
from django.urls import reverse


class BaseTestCase(DjangoTestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()

    def register_and_verify_user(
        self, username="testuser", email="test@example.com", password="testpass123"
    ):
        """
        Register a new user and verify their email.
        Returns after verification (user will be logged in).
        Use this helper in tests that need a user to exist but aren't testing registration itself.
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
                "locations": ["CABA"],
            },
        )
        self.assertRedirects(
            response, reverse("my_books")
        )  # First-time setup redirects to my_books

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
                "locations": ["CABA"],
            },
        )
        self.assertRedirects(
            response, reverse("my_books")
        )  # First-time setup redirects to my_books

        # Navigate to edit profile explicitly, edit again
        response = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Updated Name",
                "email": "test@example.com",
                "locations": ["CABA", "GBA_NORTE"],
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


class BooklistTest(BaseTestCase):
    def test_own_books_excluded(self):
        """Test that users do not see their own books in the book listing."""
        # Register first user with profile and books
        self.register_and_verify_user(username="user1", email="user1@example.com")
        self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "User One",
                "email": "user1@example.com",
                "locations": ["CABA"],
            },
        )
        self.add_books([("Book A", "Author A"), ("Book B", "Author B")])
        self.client.logout()

        # Register second user with profile and books
        self.register_and_verify_user(username="user2", email="user2@example.com")
        self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "User Two",
                "email": "user2@example.com",
                "locations": ["CABA"],
            },
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
        locations = ["CABA", "GBA_NORTE", "GBA_OESTE", "GBA_SUR"]
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
                "locations": ["CABA", "GBA_NORTE", "GBA_OESTE", "GBA_SUR"],
            },
        )

        response = self.client.get(reverse("home"))
        self.assertContains(response, "Book CABA")
        self.assertContains(response, "Book GBA_NORTE")
        self.assertContains(response, "Book GBA_OESTE")
        self.assertContains(response, "Book GBA_SUR")

        # Edit to only 2 areas - should see only those 2 books
        self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "User Five",
                "email": "user5@example.com",
                "locations": ["CABA", "GBA_NORTE"],
            },
        )

        response = self.client.get(reverse("home"))
        self.assertContains(response, "Book CABA")
        self.assertContains(response, "Book GBA_NORTE")
        self.assertNotContains(response, "Book GBA_OESTE")
        self.assertNotContains(response, "Book GBA_SUR")

    def test_request_book_exchange(self):
        """Test that exchange requests send email with contact details and requester's book list."""
        # FIXME functionality not implemented yet
        # register two users
        # first user with 3 books
        # second user two books
        # send request for second book
        # check outgoing email
        # check email content includes 2nd user contact details
        # check email content lists user books
        pass

    def test_request_book_reflected_in_profile(self):
        # FIXME human to specify
        pass

    def test_mark_as_already_requested(self):
        """Test that books already requested by a user are marked differently in the listing."""
        # FIXME functionality not implemented yet
        # register two users
        # first user with 3 books
        # second user gets home, sees all three books and Cambio button
        # send request for second book
        # request list shows 2 cambio, one ya pedido
        pass

    def test_fail_on_already_requested(self):
        """Test that users cannot request the same book twice."""
        # FIXME functionality not implemented yet
        # register two users
        # first user with 3 books
        # send request for second book, succeeds
        # send request for second book again, fails
        pass

    def test_email_error_on_exchange_request(self):
        """Test handling of email sending failures during exchange requests."""
        # TODO human to specify
        pass

    def test_error_on_request_with_no_offered(self):
        """Test that a user with no listed offered books cannot send an exchange request."""
        # TODO human to specify
        pass

    def test_error_on_request_throttled(self):
        """Test that an exchange request fails if the user has already exceeded their limit for the day."""
        # TODO human to specify
        pass

    def add_books(self, books):
        """
        Add books for the currently logged-in user.

        Args:
            books: List of (title, author) tuples
        """
        form_data = {
            "form-TOTAL_FORMS": str(len(books)),
            "form-INITIAL_FORMS": "0",
        }
        for i, (title, author) in enumerate(books):
            form_data[f"form-{i}-title"] = title
            form_data[f"form-{i}-author"] = author

        self.client.post(reverse("my_books"), form_data)
