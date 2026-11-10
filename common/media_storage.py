from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.core.files.storage import default_storage


def media_storage_key(url):
    """Return a storage key for a URL belonging to configured public media."""
    if not isinstance(url, str) or not url:
        return None

    configured = urlsplit(settings.MEDIA_URL)
    candidate = urlsplit(url)

    if candidate.query or candidate.fragment:
        return None

    if candidate.scheme != configured.scheme or candidate.netloc != configured.netloc:
        return None

    prefix = configured.path.rstrip("/") + "/"
    if not candidate.path.startswith(prefix):
        return None

    key = unquote(candidate.path[len(prefix):])

    if not key or key.startswith("/") or "\\" in key:
        return None

    if any(part in ("", ".", "..") for part in key.split("/")):
        return None

    return key


def media_file_exists(url):
    """Verify a public media reference against configured storage."""
    key = media_storage_key(url)
    return bool(key and default_storage.exists(key))
