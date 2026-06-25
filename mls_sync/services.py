import logging
from datetime import timezone
from typing import Optional

from django.db import transaction
from django.db.models import Max

from listings.models import Listing
from .client import MLSClient
from .mappers import map_property_to_listing_data
from .image_cache import cache_listing_photos

logger = logging.getLogger(__name__)


def get_latest_mls_modification_timestamp() -> Optional[str]:
    """
    Returns the greatest ModificationTimestamp we've stored, as an ISO8601 string.
    MLS Grid wants:
      ModificationTimestamp gt [GREATEST ModificationTimestamp FROM YOUR DATABASE]
    """
    agg = Listing.objects.aggregate(max_ts=Max("mls_modification_timestamp"))
    ts = agg["max_ts"]
    if not ts:
        return None

    ts = ts.astimezone(timezone.utc).replace(microsecond=0)
    return ts.isoformat().replace("+00:00", "Z")


def sync_mls_listings(updated_since: Optional[str] = None) -> int:
    """
    Fetch listings from MLS Grid, cache photos permanently, and upsert
    into the Listing model.

    Important:
    - If an existing listing already has S3 image URLs, preserve them.
    - Do not overwrite permanent S3 URLs with temporary MLSGrid URLs.
    """
    client = MLSClient()

    # If caller didn't specify, derive from DB
    if updated_since is None:
        updated_since = get_latest_mls_modification_timestamp()

    if updated_since is None:
        logger.info("No existing MLS data; performing INITIAL import (MlgCanView eq true).")
    else:
        logger.info("Replication sync from ModificationTimestamp gt %s", updated_since)

    count = 0

    for record in client.iter_properties(updated_since=updated_since):
        data = map_property_to_listing_data(record)
        mls_id = data.pop("mls_id", None)

        if not mls_id:
            logger.warning("Skipping record without ListingKey: %s", record)
            continue

        existing = Listing.objects.filter(mls_id=mls_id).first()

        existing_has_s3_images = (
            existing
            and existing.main_image_url
            and "colrealty-media.s3" in existing.main_image_url
        )

        if existing_has_s3_images:
            # Preserve permanent S3 images already cached.
            data["main_image_url"] = existing.main_image_url
            data["image_urls"] = existing.image_urls or []

        else:
            # Cache MLSGrid photos permanently into Django default storage.
            # In production, default_storage is S3.
            raw_image_urls = data.get("image_urls") or []

            if raw_image_urls:
                try:
                    main_url, cached_urls = cache_listing_photos(mls_id, raw_image_urls)

                    # Only replace with cached URLs if caching actually produced S3/permanent URLs.
                    if main_url and "colrealty-media.s3" in main_url:
                        data["main_image_url"] = main_url
                        data["image_urls"] = cached_urls
                    else:
                        logger.warning(
                            "Photo cache did not produce S3 URL for %s; keeping MLSGrid URLs temporarily.",
                            mls_id,
                        )

                except Exception as e:
                    logger.warning("Photo cache failed for %s: %s", mls_id, e)

        with transaction.atomic():
            Listing.objects.update_or_create(
                mls_id=mls_id,
                defaults=data,
            )

        count += 1

    logger.info("MLS Grid sync complete; upserted %s listings.", count)
    return count
