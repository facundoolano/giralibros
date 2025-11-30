"""
Test settings for cambiolibros project.

These settings are used when running the test suite.
Django will automatically use these settings when running tests.
"""

from .base import *  # noqa: F403, F401

# Use the same development secret key for tests
SECRET_KEY = "django-insecure-y654p_bqy%2%r+k6j&nz_g-13s)-yddz7kp73#ip42ngwprs$z"

# Debug should be False in tests to catch issues that would occur in production
DEBUG = False

ALLOWED_HOSTS = ["*"]

# Email backend - stores emails in memory for testing
# Emails can be accessed via django.core.mail.outbox in tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
