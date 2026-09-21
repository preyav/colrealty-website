"""
mls_sync/image_cache.py

Downloads MLS photos and stores them permanently in Django media storage
(local /media/ in dev, S3 in production). Returns permanent URLs that
never expire, replacing the short-lived signed MLS URLs.
"""
import random
import os
import hashlib
import logging
import time
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

# Download timeout per image
REQUEST_TIMEOUT = 15
REQUEST_DELAY = 0.3
# Only re-download if the file doesn't already exist
# (avoids re-downloading on every sync for unchanged listings)


def _get_cache_path(mls_id: str, index: int, url: str) -> str:
    """Return a stable relative path like listings/ACT12345/photo_001.jpg"""
    ext = ".jpg"
    try:
        # grab extension from URL path before query string
        raw_path = url.split("?")[0].split("/")[-1]
        if "." in raw_path:
            ext = "." + raw_path.rsplit(".", 1)[-1].lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".jpg"
    except Exception:
        pass
    return f"listings/{mls_id}/photo_{index:03d}{ext}"


def _download_and_store(url: str, rel_path: str, max_attempts: int = 5) -> str | None:
    """
    Download URL and save it to Django default storage.

    Returns the permanent storage URL on success, or None on failure.
    """
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    # Already cached — no MLS request needed.
    if default_storage.exists(rel_path):
        return default_storage.url(rel_path)

    for attempt in range(max_attempts):
        try:
            resp = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                stream=True,
            )

            if resp.status_code == 429:
                # MLS Grid is actively throttling us. Do not spend minutes
                # retrying the same image during this run.
                if attempt >= 1:
                    logger.warning(
                        "Image cache: 429 rate limit — giving up on %s "
                        "after 2 attempts; will retry on a future run",
                        rel_path,
                    )
                    return None

                wait = 3 + random.uniform(0, 2)

                logger.warning(
                    "Image cache: 429 rate limit — waiting %.1fs "
                    "before one retry",
                    wait,
                )

                time.sleep(wait)
                continue

            resp.raise_for_status()

            data = resp.content

            if len(data) < 1000:
                logger.warning(
                    "Image cache: suspiciously small response for %s",
                    rel_path,
                )
                return None

            saved_path = default_storage.save(
                rel_path,
                ContentFile(data),
            )

            return default_storage.url(saved_path)

        except Exception as e:
            logger.warning(
                "Image cache: failed to download %s — %s",
                url[:80],
                e,
            )

            if attempt < max_attempts - 1:
                wait = min(30, (2 ** attempt) + random.uniform(0, 1))
                time.sleep(wait)

    return None


def cache_listing_photos(
    mls_id: str,
    image_urls: list[str],
) -> tuple[str, list[str]]:
    """
    Download and permanently store MLS photos.

    The primary image receives additional retry attempts because it is
    used on listing cards and search results.

    Successfully cached images use permanent storage URLs.
    Failed images retain their original MLS URL as a temporary fallback.
    """
    if not image_urls:
        return "", []

    permanent_urls = []

    for i, url in enumerate(image_urls):
        if not url:
            continue

        rel_path = _get_cache_path(mls_id, i, url)

        # Main listing image is especially important.
        max_attempts = 7 if i == 0 else 5

        cached = _download_and_store(
            url,
            rel_path,
            max_attempts=max_attempts,
        )

        permanent_urls.append(
            cached if cached else url
        )

        # Give MLS Grid more breathing room.
        time.sleep(REQUEST_DELAY)

    main = permanent_urls[0] if permanent_urls else ""

    return main, permanent_urls
