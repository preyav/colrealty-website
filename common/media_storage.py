from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.core.files.storage import default_storage


def media_storage_key(url):
    """Return the storage key for a URL belonging to configured media storage."""
    if not isinstance(url, str) or not url:
        return None

    candidate = urlsplit(url)

    if candidate.query or candidate.fragment:
        return None

    # Match the URL against the configured media storage.
    # Supports both relative MEDIA_URL and absolute S3 URLs.
    configured_bases = [settings.MEDIA_URL]

    storage_base_url = getattr(default_storage, "base_url", None)
    if storage_base_url:
        configured_bases.append(storage_base_url)

    # S3Storage may not expose base_url. Derive its URL from
    # the configured backend rather than hardcoding a bucket.
    if hasattr(default_storage, "bucket_name"):
        probe_path = "__media_url_validation_probe__"
        storage_url = default_storage.url(probe_path)
        parsed_probe = urlsplit(storage_url)

        if not parsed_probe.query and not parsed_probe.fragment:
            suffix = "/" + probe_path
            if parsed_probe.path.endswith(suffix):
                configured_bases.append(
                    parsed_probe._replace(
                        path=parsed_probe.path[:-len(probe_path)],
                        query="",
                        fragment="",
                    ).geturl()
                )

    for configured_base in configured_bases:
        configured = urlsplit(configured_base)

        if (
            candidate.scheme != configured.scheme
            or candidate.netloc != configured.netloc
        ):
            continue

        prefix = configured.path.rstrip("/") + "/"

        if not candidate.path.startswith(prefix):
            continue

        key = unquote(candidate.path[len(prefix):])

        if not key or key.startswith("/") or "\\" in key:
            return None

        if any(part in ("", ".", "..") for part in key.split("/")):
            return None

        return key

    return None


def media_file_exists(url):
    """Verify a public media reference against configured storage."""
    key = media_storage_key(url)
    return bool(key and default_storage.exists(key))