"""
Development settings for cambiolibros project.

These settings are used for local development.
"""

from .base import *  # noqa: F403, F401

# SECURITY WARNING: keep the secret key used in production secret!
# This is the development secret key - production will use environment variable
SECRET_KEY = "django-insecure-y654p_bqy%2%r+k6j&nz_g-13s)-yddz7kp73#ip42ngwprs$z"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Email backend - prints emails to console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
