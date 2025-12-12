"""
Custom storage backends for static files.
"""

from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """
    ManifestStaticFilesStorage that doesn't fail on missing files.

    This is useful when CSS files reference fonts or other assets that may not
    be present in the staticfiles directory. Instead of failing, it keeps the
    original reference.
    """
    manifest_strict = False
