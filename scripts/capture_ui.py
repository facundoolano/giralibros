#!/usr/bin/env python3
"""Seed a local screenshot account and capture the feed, add-book, and profile pages."""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
USERNAME = "ui_screenshot_demo"
EMAIL = "ui-screenshot-demo@example.invalid"
PASSWORD = "local-ui-screenshots-only"
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 1000},
    "mobile": {"width": 390, "height": 844},
}
DEFAULT_PATHS = ("/", "/my/offered/", f"/profile/{USERNAME}/")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8000",
        help="Running local Django server (default: %(default)s)",
    )
    parser.add_argument(
        "--path", action="append", dest="paths",
        help="Path to capture; repeat for additional pages. Defaults to feed, add-book, profile.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=PROJECT_ROOT / "screenshots/playwright",
        help="Parent directory for timestamped capture runs (default: %(default)s)",
    )
    args = parser.parse_args()
    parsed_url = urlparse(args.base_url)
    if parsed_url.hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("This script only supports a local development server.")

    _seed_account()
    base_url = args.base_url.rstrip("/") + "/"
    output_dir = args.output_dir / datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    output_dir.mkdir(parents=True, exist_ok=False)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            # Log in once; reuse the session without saving credentials to disk.
            login_context = browser.new_context()
            try:
                page = login_context.new_page()
                page.goto(urljoin(base_url, "login/"), wait_until="networkidle")
                page.locator('input[name="username"]').fill(USERNAME)
                page.locator('input[name="password"]').fill(PASSWORD)
                page.locator('button[type="submit"]').click()
                page.wait_for_url(base_url, wait_until="networkidle")
                state = login_context.storage_state()
            finally:
                login_context.close()

            for name, viewport in VIEWPORTS.items():
                context = browser.new_context(viewport=viewport, storage_state=state)
                try:
                    page = context.new_page()
                    for path in args.paths or DEFAULT_PATHS:
                        _capture(page, base_url, path, output_dir, name)
                finally:
                    context.close()
        finally:
            browser.close()


def _seed_account() -> None:
    """Create demo records with independent cover files, leaving existing users untouched."""
    sys.path.insert(0, str(PROJECT_ROOT))
    os.environ["DJANGO_SETTINGS_MODULE"] = "giralibros.settings.development"
    import django

    django.setup()
    from django.conf import settings
    from django.contrib.auth.models import User
    from django.core.files import File
    from django.db import transaction
    from books.models import OfferedBook, UserProfile, WantedBook

    if Path(settings.DATABASES["default"]["NAME"]).resolve() != PROJECT_ROOT / "db.sqlite3":
        raise RuntimeError("Refusing to seed anything other than the local db.sqlite3.")

    sources = []
    for book in OfferedBook.objects.exclude(user__username=USERNAME).exclude(
        cover_image=""
    ).exclude(cover_image__isnull=True).order_by("pk").iterator():
        if book.cover_image.storage.exists(book.cover_image.name):
            sources.append(book)
        if len(sources) == 3:
            break
    if len(sources) < 3:
        raise RuntimeError("Need at least three existing books with valid local cover files.")

    with transaction.atomic():
        user, created = User.objects.get_or_create(
            username=USERNAME, defaults={"email": EMAIL, "first_name": "Demo"}
        )
        if not created and (user.email != EMAIL or user.is_staff or user.is_superuser):
            raise RuntimeError(f"Username {USERNAME!r} is already used by another account.")
        if created or not user.check_password(PASSWORD):
            user.set_password(PASSWORD)
            user.save(update_fields=["password"])
        if not user.is_active:
            raise RuntimeError("The screenshot account is inactive; not changing its status.")
        UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "contact_email": EMAIL,
                "about": "Me gusta leer y compartir libros. Podemos coordinar cambios en Buenos Aires.",
            },
        )
        # Each demo book owns its file; deleting it cannot delete an original cover.
        for source in sources:
            book, created = OfferedBook.objects.get_or_create(
                user=user, title=source.title, author=source.author,
                defaults={"notes": source.notes or "En buen estado. Disponible para intercambio."},
            )
            if not book.cover_image:
                with source.cover_image.open("rb") as cover:
                    book.cover_image.save(
                        f"ui-demo-{source.pk}{Path(source.cover_image.name).suffix}",
                        File(cover),
                    )
        WantedBook.objects.get_or_create(
            user=user, title=sources[0].title, author=sources[0].author
        )
    print(f"Screenshot account ready: {USERNAME} (existing users unchanged)")


def _capture(
    page: Page, base_url: str, path: str, output_dir: Path, viewport_name: str
) -> None:
    url = urljoin(base_url, path.lstrip("/"))
    response = page.goto(url, wait_until="networkidle")
    if response and response.status >= 400:
        raise RuntimeError(f"{url} returned HTTP {response.status}")
    if urlparse(page.url).path != urlparse(url).path:
        raise RuntimeError(f"Unexpected redirect: {url} -> {page.url}")
    page.evaluate("document.fonts.ready")
    page.evaluate("""async () => {
        await Promise.all(Array.from(document.images, image =>
            image.decode().catch(() => {})
        ));
    }""")
    parsed = urlparse(path)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", parsed.path.strip("/") or "home")
    if parsed.query:
        slug += "-" + re.sub(r"[^a-zA-Z0-9_-]+", "-", parsed.query)
    filename = f"{slug}-{viewport_name}.png"
    page.screenshot(path=output_dir / filename, full_page=True, animations="disabled")
    print(f"Saved {output_dir / filename}")


if __name__ == "__main__":
    main()
