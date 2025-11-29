from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import Client
from django.test import TestCase as DjangoTestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


class BaseTestCase(DjangoTestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()

    def register_and_verify_user(self, username="testuser", email="test@example.com", password="testpass123"):
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

        FIXME: This is a temporary workaround that accesses the database directly.
        Once email sending is implemented in the register view, this should be
        replaced with Django's mail.outbox to capture the verification URL from
        the actual email content, which qualifies as observable behavior.
        See: https://docs.djangoproject.com/en/stable/topics/testing/tools/#email-services
        """
        user = User.objects.get(email=email)
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        return reverse("verify_email", kwargs={"uidb64": uid, "token": token})


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
        # Register and verify user
        self.register_and_verify_user()

        # Clear session (verification auto-logs user in)
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
        # Register and verify user
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
        # Register and verify user
        self.register_and_verify_user()

        # Logout
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
        self.assertContains(response, "Este usuario ya está registrado")  # Error message

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
        # Register and verify user
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
        self.assertRedirects(response, reverse("my_books"))  # First-time setup redirects to my_books

        # Navigate to home, should now stay on home
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)  # Successfully loads home page

    def test_profile_view_profile_afer_edit(self):
        """Test profile viewing behavior after editing."""
        # register + verify user
        # login, redirects to edit profile
        # save minimum profile data
        # navigate to edit profile explicitly, edit again
        # redirects or responds with view profile
        pass

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
        # register two users, both in CABA, two books each
        # check that each sees only the other one's book not their owns
        pass

    def test_filter_by_location(self):
        """Test that book listings are filtered based on user's selected location areas."""
        # register 5 users
        # for the first 4 users, add 1 book, edit to each different location

        # user 5 set in all areas, sees all books
        # edit to 2 areas, sees only those 2 areas books
        pass

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
