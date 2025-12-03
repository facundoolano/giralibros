"""
Production settings for giralibros project.

These settings are used for production deployment.
Sensitive values are loaded from environment variables.
"""

import os

from .base import *  # noqa: F403, F401

STATIC_ROOT = os.environ.get("STATIC_ROOT", "/var/www/giralibros/static")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY environment variable must be set in production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Allow specific hosts in production
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

# Feature flags
# Disable registration by default in production (can be enabled via env var)
REGISTRATION_ENABLED = os.environ.get("REGISTRATION_ENABLED", "False") == "True"

# Email backend - SMTP for production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# SMTP settings (to be configured when setting up email service)
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")

# Security settings for production
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
