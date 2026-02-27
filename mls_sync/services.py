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

        # ── Cache photos permanently so MLS signed URLs don't expire ──────
        raw_image_urls = data.get("image_urls") or []
        if raw_image_urls:
            try:
                main_url, cached_urls = cache_listing_photos(mls_id, raw_image_urls)
                data["main_image_url"] = main_url
                data["image_urls"] = cached_urls
            except Exception as e:
                # Photo caching failed — keep original MLS URLs as fallback
                # so the listing still syncs even if image download breaks
                logger.warning("Photo cache failed for %s: %s", mls_id, e)
        # ──────────────────────────────────────────────────────────────────

        with transaction.atomic():
            Listing.objects.update_or_create(
                mls_id=mls_id,
                defaults=data,
            )

        count += 1

    logger.info("MLS Grid sync complete; upserted %s listings.", count)
    return count
