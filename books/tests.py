from django.test import Client
from django.test import TestCase as DjangoTestCase


class BaseTestCase(DjangoTestCase):
    def setUp(self):
        # Every test needs a client.
        self.client = Client()

    # TODO add register user helper


# Create your tests here.
class UserTest(BaseTestCase):
    def test_login_register(self):
        # test with unexistent user fails
        # register user with same credentials
        # follow verify link
        # try login again and it works
        pass

    def test_login_no_verified_fails(self):
        # register user without verifying
        # try login, fails
        # verify
        # try login, succeeds
        pass

    def test_login_wrong_password(self):
        # register + verify user
        # wrong password fails with error message
        pass

    def test_home_needs_login(self):
        # register + verify user
        # try navigate to home, redirects to login
        # login, redirects to home
        pass

    def test_logout_redirects(self):
        # register + verify user
        # login, redirects to home
        # logout, redirects to login
        # try navigate to home, redirects to login
        pass

    def test_login_username(self):
        # register + verify user
        # login with username, succeeds
        # logout
        # login with email, succeeds
        pass

    def test_register_fails_repeated_credentials(self):
        # register user without verifying
        # try to register again same username, fails
        # try to register again same email, fails
        pass

    def test_home_redirects_on_no_profile(self):
        # register + verify user
        # login, redirects to edit profile
        # navigate to home, redirects to edit profile
        # save minimum profile data, redirects to my books
        # navigate to home, stays in home
        pass

    def test_profile_view_profile_afer_edit(self):
        # TODO human to specify
        pass

    def test_profile_edit_validations(self):
        # TODO human to specify
        pass

    def test_throttle_registration_attempts(self):
        # TODO human to specify
        pass


class BooklistTest(BaseTestCase):
    def own_books_excluded(self):
        # register two users, both in CABA, two books each
        # check that each sees only the other one's book not their owns
        pass

    def filter_by_location(self):
        # register 5 users
        # for the first 4 users, add 1 book, edit to each different location

        # user 5 set in all areas, sees all books
        # edit to 2 areas, sees only those 2 areas books
        pass

    def request_book_exchange(self):
        # register two users
        # first user with 3 books
        # second user two books
        # send request for second book
        # check outgoing email
        # check email content includes 2nd user contact details
        # check email content lists user books
        pass

    def mark_as_already_requested(self):
        # register two users
        # first user with 3 books
        # second user gets home, sees all three books and Cambio button
        # send request for second book
        # request list shows 2 cambio, one ya pedido
        pass

    def fail_on_already_requested(self):
        # register two users
        # first user with 3 books
        # send request for second book, succeeds
        # send request for second book again, fails
        pass

    def test_email_error_on_exchange_request(self):
        # TODO human to specify
        pass
