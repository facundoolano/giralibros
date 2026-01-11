from unittest.mock import patch

from django.core import mail
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse


class BookTestMixin:
    """Mixin with common test helpers for book-related tests. Use with TestCase or TransactionTestCase."""

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
                "password1": password,
                "password2": password,
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
        return self._get_url_from_email(email, "/verify/")

    def get_password_reset_url_from_email(self, email):
        """
        Extract password reset URL from email sent during password reset request.
        """
        return self._get_url_from_email(email, "/password-reset/")

    def _get_url_from_email(self, email, url_pattern):
        """
        Extract URL containing a specific pattern from email body.

        Args:
            email: Email address to search for
            url_pattern: URL pattern to find (e.g., "/verify/", "/password-reset/")
        """
        # Find the most recent email sent to this address
        sent_email = None
        for email_msg in reversed(mail.outbox):
            if email in email_msg.to:
                sent_email = email_msg
                break

        if not sent_email:
            raise AssertionError(f"No email found for {email}")

        # Extract the URL from the email body
        email_body = sent_email.body
        lines = email_body.split("\n")
        for line in lines:
            if url_pattern in line:
                return line.strip()

        raise AssertionError(f"No URL with pattern '{url_pattern}' found in email body")

    def add_books(self, books, wanted=False):
        """
        Add books for the currently logged-in user.

        Args:
            books: List of (title, author) tuples
            wanted: If True, adds wanted books; otherwise adds offered books
        """
        if wanted:
            # Wanted books use single-form approach
            for title, author in books:
                self.client.post(
                    reverse("my_wanted"),
                    {"title": title, "author": author},
                )
        else:
            # Offered books use single-form approach
            for title, author in books:
                self.client.post(
                    reverse("my_offered"),
                    {"title": title, "author": author},
                )


# Create your tests here.
class UserTest(BookTestMixin, TestCase):
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
                "password1": "testpass123",
                "password2": "testpass123",
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
                "password1": "testpass123",
                "password2": "testpass123",
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

    def test_wrong_verification_code(self):
        """Test that a registered user cannot log in after entering the wrong verification code."""
        # Register first user
        response = self.client.post(
            reverse("register"),
            {
                "username": "testuser",
                "email": "test@example.com",
                "password1": "testpass123",
                "password2": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)

        # Register second user
        response = self.client.post(
            reverse("register"),
            {
                "username": "testuser2",
                "email": "test2@example.com",
                "password1": "testpass456",
                "password2": "testpass456",
            },
        )
        self.assertEqual(response.status_code, 200)

        # Get verification URLs from emails
        verify_url_user1 = self.get_verification_url_from_email("test@example.com")
        verify_url_user2 = self.get_verification_url_from_email("test2@example.com")

        # Parse URLs to extract uidb64 and token
        # URL format: http://testserver/verify/{uidb64}/{token}/
        parts_user1 = verify_url_user1.rstrip("/").split("/")
        uidb64_user1 = parts_user1[-2]

        parts_user2 = verify_url_user2.rstrip("/").split("/")
        token_user2 = parts_user2[-1]

        # Construct mismatched URL: user 1's uidb64 with user 2's token
        wrong_verification_url = f"/verify/{uidb64_user1}/{token_user2}/"

        # Try to verify with wrong token
        response = self.client.get(wrong_verification_url)
        self.assertEqual(response.status_code, 200)
        # Should show verification failed page
        self.assertContains(response, "inválido")  # Verification failed message

        # Try to login, should fail because user is not verified
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

        # Verify logout cleared authentication by accessing a protected view
        response = self.client.get(reverse("profile_edit"))
        self.assertRedirects(response, reverse("login") + "?next=/profile/edit/")

    def test_login_next_honored(self):
        """Test that after login, user is redirected to the ?next parameter URL."""
        self.register_and_verify_user()

        # Logout
        self.client.logout()

        # Try to navigate to own profile (requires login)
        profile_url = reverse("profile", kwargs={"username": "testuser"})
        response = self.client.get(profile_url)

        # Should redirect to login with ?next parameter
        expected_redirect = reverse("login") + f"?next={profile_url}"
        self.assertRedirects(response, expected_redirect)

        # Now login by posting to the login form with ?next in URL
        # The form has no action attribute, so it posts to current URL (preserving query params)
        response = self.client.post(
            reverse("login") + f"?next={profile_url}",
            {
                "username": "testuser",
                "password": "testpass123",
            },
        )

        # Should redirect to the original profile URL, not home
        self.assertRedirects(response, profile_url)

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
                "password1": "testpass123",
                "password2": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)

        # Try to register again with same username, should fail
        response = self.client.post(
            reverse("register"),
            {
                "username": "testuser",
                "email": "different@example.com",
                "password1": "testpass123",
                "password2": "testpass123",
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
                "password1": "testpass123",
                "password2": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 200)  # Stays on form
        self.assertContains(response, "Este email ya está registrado")  # Error message

    def test_register_weak_password_fails(self):
        """Test that registration enforces strong password requirements."""
        # Try to register with password that's too short
        response = self.client.post(
            reverse("register"),
            {
                "username": "testuser",
                "email": "test@example.com",
                "password1": "short",
                "password2": "short",
            },
        )
        self.assertEqual(response.status_code, 200)  # Stays on form
        self.assertContains(
            response, "La contraseña es demasiado corta"
        )  # Error message

        # Try to register with all-numeric password
        response = self.client.post(
            reverse("register"),
            {
                "username": "testuser2",
                "email": "test2@example.com",
                "password1": "1111333777",
                "password2": "1111333777",
            },
        )
        self.assertEqual(response.status_code, 200)  # Stays on form
        self.assertContains(
            response, "La contraseña está formada completamente por dígitos"
        )  # Error message

        # Try to register with common password
        response = self.client.post(
            reverse("register"),
            {
                "username": "testuser3",
                "email": "test3@example.com",
                "password1": "password",
                "password2": "password",
            },
        )
        self.assertEqual(response.status_code, 200)  # Stays on form
        self.assertContains(
            response, "La contraseña tiene un valor demasiado común"
        )  # Error message

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
            response, reverse("home")
        )  # First-time setup redirects to home

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
            response, reverse("home")
        )  # First-time setup redirects to home

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

    def test_password_reset_login_with_new_password(self):
        """Test that user can login after resetting password with new password."""
        # Register and verify user
        self.register_and_verify_user()
        self.client.logout()

        # Request password reset
        response = self.client.post(
            reverse("password_reset_request"),
            {"email": "test@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)  # Confirmation page

        # Extract reset URL from email
        reset_url = self.get_password_reset_url_from_email("test@example.com")

        # GET reset link to validate token (Django redirects to set-password URL)
        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 302)
        set_password_url = response.url

        # POST to set new password
        response = self.client.post(
            set_password_url,
            {
                "new_password1": "newpassword123",
                "new_password2": "newpassword123",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contraseña cambiada")

        # Try login with new password, should succeed
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": "newpassword123",
            },
        )
        self.assertEqual(response.status_code, 302)  # Redirects after successful login

    def test_password_reset_old_password_invalid(self):
        """Test that user can't login using old password after resetting."""
        # Register and verify user
        self.register_and_verify_user()
        self.client.logout()

        # Request password reset
        response = self.client.post(
            reverse("password_reset_request"),
            {"email": "test@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # Extract reset URL from email
        reset_url = self.get_password_reset_url_from_email("test@example.com")

        # GET reset link to validate token
        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 302)
        set_password_url = response.url

        # POST to set new password
        response = self.client.post(
            set_password_url,
            {
                "new_password1": "newpassword123",
                "new_password2": "newpassword123",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # Try login with old password, should fail
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": "testpass123",  # Old password
            },
        )
        self.assertEqual(response.status_code, 200)  # Stays on login page
        self.assertContains(
            response, "Por favor introduzca un nombre de usuario"
        )  # Error message

    def test_password_reset_invalid_token(self):
        """Test that password is not reset if the token format is invalid."""
        # Register and verify user
        self.register_and_verify_user()
        self.client.logout()

        # Try to use a malformed token
        invalid_url = "/password-reset/MQ/invalid-token-12345/"
        response = self.client.get(invalid_url)
        self.assertEqual(response.status_code, 200)

        # Try to POST to invalid token
        response = self.client.post(
            invalid_url,
            {
                "new_password1": "newpassword123",
                "new_password2": "newpassword123",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # Old password should still work
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": "testpass123",  # Old password
            },
        )
        self.assertEqual(response.status_code, 302)  # Login succeeds

    def test_password_reset_wrong_user_token(self):
        """Test that password is not reset when using another user's valid token."""
        # Register and verify first user
        self.register_and_verify_user()
        self.client.logout()

        # Register second user
        self.register_and_verify_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass456",
        )
        self.client.logout()

        # Request password reset for user 1
        response = self.client.post(
            reverse("password_reset_request"),
            {"email": "test@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # Request password reset for user 2
        response = self.client.post(
            reverse("password_reset_request"),
            {"email": "test2@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # Get reset URLs from emails
        reset_url_user1 = self.get_password_reset_url_from_email("test@example.com")
        reset_url_user2 = self.get_password_reset_url_from_email("test2@example.com")

        # Parse URLs to extract uidb64 and token
        # URL format: http://testserver/password-reset/{uidb64}/{token}/
        parts_user1 = reset_url_user1.rstrip("/").split("/")
        uidb64_user1 = parts_user1[-2]
        token_user1 = parts_user1[-1]

        parts_user2 = reset_url_user2.rstrip("/").split("/")
        uidb64_user2 = parts_user2[-2]
        token_user2 = parts_user2[-1]

        # Construct mismatched URL: user 2's uidb64 with user 1's token
        wrong_user_url = f"/password-reset/{uidb64_user2}/{token_user1}/"

        # GET with mismatched token (Django validates and may show disabled form)
        response = self.client.get(wrong_user_url)

        # Try to reset user 2's password with user 1's token
        response = self.client.post(
            wrong_user_url,
            {
                "new_password1": "hackedpassword123",
                "new_password2": "hackedpassword123",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # User 2's original password should still work
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser2",
                "password": "testpass456",  # Original password
            },
        )
        self.assertEqual(response.status_code, 302)  # Login succeeds

    def test_password_reset_weak_password_fails(self):
        """Test that password reset form enforces same validations as registration."""
        # Register and verify user
        self.register_and_verify_user()
        self.client.logout()

        # Request password reset
        response = self.client.post(
            reverse("password_reset_request"),
            {"email": "test@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # Extract reset URL from email
        reset_url = self.get_password_reset_url_from_email("test@example.com")

        # GET reset link to validate token
        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 302)
        set_password_url = response.url

        # Try to set password that's too short
        response = self.client.post(
            set_password_url,
            {
                "new_password1": "short",
                "new_password2": "short",
            },
        )
        self.assertEqual(response.status_code, 200)  # Stays on form
        self.assertContains(
            response, "La contraseña es demasiado corta"
        )  # Error message

        # Try to set all-numeric password
        response = self.client.post(
            set_password_url,
            {
                "new_password1": "1111333777",
                "new_password2": "1111333777",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "La contraseña está formada completamente por dígitos"
        )

        # Try to set common password
        response = self.client.post(
            set_password_url,
            {
                "new_password1": "password",
                "new_password2": "password",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La contraseña tiene un valor demasiado común")


class BooksTest(BookTestMixin, TestCase):
    def test_own_books_not_excluded(self):
        """Test that users see their own books in the book listing."""
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

        # User 2 should see both their books and user 1's
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Book A")
        self.assertContains(response, "Book B")
        self.assertContains(response, "Book C")
        self.assertContains(response, "Book D")

    def test_default_all_locations(self):
        """Test that by default, users see books from all locations."""
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

        # Register user 5 with only 2 locations
        self.register_and_verify_user(username="user5", email="user5@example.com")
        self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "User Five",
                "email": "user5@example.com",
                "locations": ["CABA_CENTRO", "GBA_NORTE"],
            },
        )

        # Without my_locations param, should see all books regardless of user's locations
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Book CABA_CENTRO")
        self.assertContains(response, "Book GBA_NORTE")
        self.assertContains(response, "Book GBA_OESTE")
        self.assertContains(response, "Book GBA_SUR")

    def test_filter_by_location(self):
        """Test that ?my_locations filters books by user's selected location areas."""
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

        # Register user 5 with 2 locations
        self.register_and_verify_user(username="user5", email="user5@example.com")
        self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "User Five",
                "email": "user5@example.com",
                "locations": ["CABA_CENTRO", "GBA_NORTE"],
            },
        )

        # With my_locations param, should see only books from user's locations
        response = self.client.get(reverse("home") + "?my_locations")
        self.assertContains(response, "Book CABA_CENTRO")
        self.assertContains(response, "Book GBA_NORTE")
        self.assertNotContains(response, "Book GBA_OESTE")
        self.assertNotContains(response, "Book GBA_SUR")

        # Edit user to have all 4 locations
        self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "User Five",
                "email": "user5@example.com",
                "locations": ["CABA_CENTRO", "GBA_NORTE", "GBA_OESTE", "GBA_SUR"],
            },
        )

        # With my_locations param and all locations, should see all books
        response = self.client.get(reverse("home") + "?my_locations")
        self.assertContains(response, "Book CABA_CENTRO")
        self.assertContains(response, "Book GBA_NORTE")
        self.assertContains(response, "Book GBA_OESTE")
        self.assertContains(response, "Book GBA_SUR")

    def test_anonymous_user_home(self):
        """Test that a logged out user sees available books from all locations"""
        # Register 3 users with books
        for i in range(3):
            username = f"user{i + 1}"
            email = f"user{i + 1}@example.com"
            self.register_and_verify_user(
                username=username, email=email, fill_profile=True
            )
            self.add_books([(f"Book {i + 1}", f"Author {i + 1}")])
            self.client.logout()

        # Access home page as anonymous user
        response = self.client.get(reverse("home"))

        # Should return 200 (not redirect to login)
        self.assertEqual(response.status_code, 200)

        # Should see all books (no location filtering)
        self.assertContains(response, "Book 1")
        self.assertContains(response, "Book 2")
        self.assertContains(response, "Book 3")

        # Should see welcome text for anonymous users
        self.assertContains(response, "GiraLibros")
        self.assertContains(response, "Registrate")
        self.assertContains(response, "Iniciá sesión")

        # Should NOT see usernames
        self.assertNotContains(response, "user1")
        self.assertNotContains(response, "user2")
        self.assertNotContains(response, "user3")

        # Should NOT see "Cambio" button (exchange button)
        self.assertNotContains(response, "Cambio")

    def test_text_search(self):
        """Test that text search filters books by normalized title and author with accent-insensitive matching."""
        # Register first user with 4 books (2 by same author)
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books(
            [
                ("Rayuela", "Julio Cortázar"),
                ("Bestiario", "Julio Cortázar"),
                ("Ficciones", "Jorge Luis Borges"),
                ("El Aleph", "Jorge Luis Borges"),
            ]
        )
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
        self.add_books(
            [
                ("Rayuela", "Julio Cortázar"),
                ("Ficciones", "Jorge Luis Borges"),
                ("El túnel", "Ernesto Sábato"),
                ("Cien años de soledad", "Gabriel García Márquez"),
            ]
        )
        self.client.logout()

        # Register second user with wanted books
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        # Add offered book (needed to see other users' books)
        self.add_books([("Book B", "Author B")])
        # Add wanted books
        self.add_books(
            [
                ("Rayuela", "Julio Cortázar"),
                ("Ficciones", "Jorge Luis Borges"),
            ],
            wanted=True,
        )

        # Filter by wanted books - should only show matching books
        response = self.client.get(reverse("home"), {"wanted": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rayuela")
        self.assertContains(response, "Ficciones")
        self.assertNotContains(response, "El túnel")
        self.assertNotContains(response, "Cien años de soledad")

        # Should handle accent variations (wanted without accent matches offered with accent)
        self.add_books(
            [("Cronica de una muerte anunciada", "Garcia Marquez")], wanted=True
        )
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
        book = offered_books[1]

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
        book = offered_books[1]

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
        book = offered_books[1]
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
        book = offered_books[1]

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
        book = offered_books[1]

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
        self.assertEqual(len(offered_books), 4)

        # First request should succeed
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": offered_books[1].id})
        )
        self.assertEqual(response.status_code, 201)

        # Second request should succeed
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": offered_books[2].id})
        )
        self.assertEqual(response.status_code, 201)

        # Third request should fail due to throttling
        response = self.client.post(
            reverse("request_exchange", kwargs={"book_id": offered_books[3].id})
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

    def test_filter_by_wanted(self):
        """Test filtering offered book by wanted including author-only wanted."""
        # Register first user with several books from different authors
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        self.add_books(
            [
                ("Rayuela", "Julio Cortázar"),
                ("Bestiario", "Julio Cortázar"),
                ("Ficciones", "Jorge Luis Borges"),
                ("El Aleph", "Jorge Luis Borges"),
                ("El túnel", "Ernesto Sábato"),
            ]
        )
        self.client.logout()

        # Register second user with wanted books
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )
        # Add offered book (needed to see other users' books)
        self.add_books([("Book B", "Author B")])
        # Add wanted books: one specific title, one author-only (empty title)
        self.add_books(
            [
                ("Ficciones", "Jorge Luis Borges"),  # Specific book
                ("", "Julio Cortázar"),  # Author-only (any book by this author)
            ],
            wanted=True,
        )

        # Filter by wanted books
        response = self.client.get(reverse("home"), {"wanted": ""})
        self.assertEqual(response.status_code, 200)

        # Should match the specific book "Ficciones"
        self.assertContains(response, "Ficciones")

        # Should match both books by Cortázar (author-only wanted)
        self.assertContains(response, "Rayuela")
        self.assertContains(response, "Bestiario")

        # Should NOT match "El Aleph" (same author as Ficciones, but not wanted)
        self.assertNotContains(response, "El Aleph")

        # Should NOT match "El túnel" (different author)
        self.assertNotContains(response, "El túnel")


class BooksPaginationTest(BookTestMixin, TestCase):
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
        self.assertContains(response, "Book 5")  # 20th book
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
            reverse("home") + "?page=2", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
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
            reverse("home") + "?page=1", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Page 1 should have 20 books and indicate next page
        self.assertTrue(data["has_next"])
        self.assertEqual(data["next_page"], 2)

    def test_anonymous_user_pagination(self):
        """Test that pagination works for anonymous users."""
        # Register user with 25 books
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )
        books = [(f"Book {i}", f"Author {i}") for i in range(25)]
        self.add_books(books)
        self.client.logout()

        # Access home as anonymous user - first page should show 20 books
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        offered_books = response.context["offered_books"]
        self.assertEqual(len(offered_books), 20)

        # Should indicate more pages available
        self.assertTrue(response.context["has_next"])

        # Test AJAX pagination for page 2
        response = self.client.get(
            reverse("home") + "?page=2", HTTP_X_REQUESTED_WITH="XMLHttpRequest"
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

        # HTML should contain the last 5 books (0-4)
        self.assertIn("Book 4", data["html"])
        self.assertIn("Book 0", data["html"])

        # Should NOT leak usernames
        self.assertNotIn("user1", data["html"])

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


class BookCoverTest(BookTestMixin, TransactionTestCase):
    """
    Tests for book cover upload and cleanup functionality.

    Note: Uses TransactionTestCase instead of TestCase because django-cleanup
    requires actual transaction commits to trigger file cleanup callbacks.
    """

    def test_cover_upload(self):
        """Test that users can upload a cover image for their book and it displays in their profile."""
        # Register and verify user
        self.register_and_verify_user(fill_profile=True)

        # Add a book
        self.add_books([("Test Book", "Test Author")])

        # Get the book ID from the profile page
        response = self.client.get(reverse("profile", kwargs={"username": "testuser"}))
        offered_books = response.context["offered_books"]
        book = offered_books[0]

        # Create a test image file
        image_file = self.create_test_image()

        # Upload the cover image via AJAX
        response = self.client.post(
            reverse("upload_book_photo", kwargs={"book_id": book.id}),
            {"cover_image": image_file},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

        # Get the image URL from the JSON response
        response_data = response.json()
        self.assertIn("image_url", response_data)
        image_url = response_data["image_url"]

        # Request own profile, verify the image URL is in the HTML
        response = self.client.get(reverse("profile", kwargs={"username": "testuser"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, image_url)

        # Verify the cover image file exists on disk
        self.assertTrue(self.file_exists(image_url))

    def test_cover_display_in_list(self):
        """Test that cover images uploaded by one user are displayed in other users' book listings."""
        # Register and verify first user
        self.register_and_verify_user(
            username="user1", email="user1@example.com", fill_profile=True
        )

        # Add a book
        self.add_books([("Test Book", "Test Author")])

        # Get the book ID and upload a cover
        response = self.client.get(reverse("profile", kwargs={"username": "user1"}))
        offered_books = response.context["offered_books"]
        book = offered_books[0]

        image_file = self.create_test_image()
        response = self.client.post(
            reverse("upload_book_photo", kwargs={"book_id": book.id}),
            {"cover_image": image_file},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        image_url = response_data["image_url"]

        self.client.logout()

        # Register and verify second user in same location
        self.register_and_verify_user(
            username="user2", email="user2@example.com", fill_profile=True
        )

        # Verify user1's book with cover appears in user2's home listing
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Book")
        self.assertContains(response, image_url)

    def test_cleanup_after_cover_update(self):
        """Test that old cover images are deleted when replaced with new ones."""
        # Register and verify user
        self.register_and_verify_user(fill_profile=True)

        # Add a book
        self.add_books([("Test Book", "Test Author")])

        # Get the book ID from profile
        response = self.client.get(reverse("profile", kwargs={"username": "testuser"}))
        offered_books = response.context["offered_books"]
        book = offered_books[0]

        # Upload first cover image
        image_file = self.create_test_image("first_cover.jpg")
        response = self.client.post(
            reverse("upload_book_photo", kwargs={"book_id": book.id}),
            {"cover_image": image_file},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        old_image_url = response_data["image_url"]

        # Verify first image exists
        self.assertTrue(self.file_exists(old_image_url))

        # Upload second cover image to replace the first
        image_file = self.create_test_image("second_cover.jpg")
        response = self.client.post(
            reverse("upload_book_photo", kwargs={"book_id": book.id}),
            {"cover_image": image_file},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        new_image_url = response_data["image_url"]

        # Verify we got a different URL
        self.assertNotEqual(old_image_url, new_image_url)

        # Verify new image exists
        self.assertTrue(self.file_exists(new_image_url))

        # Verify old image was cleaned up by django-cleanup
        self.assertFalse(self.file_exists(old_image_url))

        # Verify profile shows the new image URL
        response = self.client.get(reverse("profile", kwargs={"username": "testuser"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, new_image_url)
        self.assertNotContains(response, old_image_url)

    def test_cleanup_after_book_removal(self):
        """Test that cover images are deleted when their associated book is removed."""
        # Register and verify user
        self.register_and_verify_user(fill_profile=True)

        # Add a book
        self.add_books([("Test Book", "Test Author")])

        # Get the book ID and upload a cover
        response = self.client.get(reverse("profile", kwargs={"username": "testuser"}))
        offered_books = response.context["offered_books"]
        book = offered_books[0]

        image_file = self.create_test_image()
        response = self.client.post(
            reverse("upload_book_photo", kwargs={"book_id": book.id}),
            {"cover_image": image_file},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

        response_data = response.json()
        image_url = response_data["image_url"]

        # Verify image exists
        self.assertTrue(self.file_exists(image_url))

        # Remove the book using the delete endpoint
        response = self.client.post(
            reverse("delete_offered_book", kwargs={"book_id": book.id}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)

        # Verify profile no longer shows the book in offered books section
        response = self.client.get(reverse("profile", kwargs={"username": "testuser"}))
        self.assertEqual(response.status_code, 200)
        offered_books = response.context["offered_books"]
        self.assertEqual(len(offered_books), 0)
        self.assertNotContains(response, image_url)

        # Verify image file was cleaned up
        self.assertFalse(self.file_exists(image_url))

    def test_cover_upload_fails_on_non_image_file(self):
        """Test that uploading a non-image file is rejected with an error."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Register and verify user
        self.register_and_verify_user(fill_profile=True)

        # Add a book
        self.add_books([("Test Book", "Test Author")])

        # Get the book ID
        response = self.client.get(reverse("profile", kwargs={"username": "testuser"}))
        offered_books = response.context["offered_books"]
        book = offered_books[0]

        # Create a text file instead of an image
        text_file = SimpleUploadedFile(
            "test.txt", b"This is not an image", content_type="text/plain"
        )

        # Attempt to upload the text file as a cover
        response = self.client.post(
            reverse("upload_book_photo", kwargs={"book_id": book.id}),
            {"cover_image": text_file},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        # Should fail with bad request
        self.assertEqual(response.status_code, 400)

    def create_test_image(self, filename="test_cover.jpg"):
        """
        Create a minimal test image file for upload testing.

        Args:
            filename: Name for the uploaded file

        Returns:
            SimpleUploadedFile with a minimal JPEG image
        """
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        # Create a minimal test image (10x10 red square)
        image = Image.new("RGB", (10, 10), color="red")
        image_io = BytesIO()
        image.save(image_io, format="JPEG")
        image_io.seek(0)

        return SimpleUploadedFile(
            filename, image_io.getvalue(), content_type="image/jpeg"
        )

    def file_exists(self, image_url):
        """
        Check if a cover image file exists on disk given its URL.

        Note: Ideally we wouldn't access the filesystem directly or make assumptions
        about storage, but Django's test client doesn't serve media files by default,
        so we verify file existence on disk to test cleanup behavior.

        Args:
            image_url: The URL path to the image (e.g., /media/book_covers/...)

        Returns:
            True if the file exists on disk, False otherwise
        """
        import os

        from django.conf import settings

        # Extract relative path from URL and check filesystem
        image_path = image_url.replace(settings.MEDIA_URL, "")
        full_path = os.path.join(settings.MEDIA_ROOT, image_path)
        return os.path.exists(full_path)
