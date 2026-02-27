"""
mls_sync/image_cache.py

Downloads MLS photos and stores them permanently in Django media storage
(local /media/ in dev, S3 in production). Returns permanent URLs that
never expire, replacing the short-lived signed MLS URLs.
"""
import os
import hashlib
import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

# Download timeout per image
REQUEST_TIMEOUT = 15

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


def _download_and_store(url: str, rel_path: str) -> str | None:
    """
    Download url and save to Django default storage at rel_path.
    Returns the public URL, or None on failure.
    """
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    # Already cached — return existing URL
    if default_storage.exists(rel_path):
        return default_storage.url(rel_path)

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True)
        resp.raise_for_status()
        data = resp.content
        if len(data) < 1000:          # suspiciously small = probably an error page
            return None
        default_storage.save(rel_path, ContentFile(data))
        return default_storage.url(rel_path)
    except Exception as e:
        logger.warning(f"Image cache: failed to download {url[:80]}… — {e}")
        return None


def cache_listing_photos(mls_id: str, image_urls: list[str]) -> tuple[str, list[str]]:
    """
    Download and permanently store all photos for a listing.

    Returns (main_image_url, image_urls) with permanent URLs.
    Falls back to original MLS URL if download fails so the page still
    shows something (even if it expires later).
    """
    if not image_urls:
        return "", []

    permanent_urls = []
    for i, url in enumerate(image_urls):
        if not url:
            continue
        rel_path = _get_cache_path(mls_id, i, url)
        cached = _download_and_store(url, rel_path)
        # Use cached URL if successful, otherwise keep original as fallback
        permanent_urls.append(cached if cached else url)

    main = permanent_urls[0] if permanent_urls else ""
    return main, permanent_urls
