import logging
from datetime import timezone
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Max

from listings.models import Listing
from .client import MLSClient
from .mappers import map_property_to_listing_data

logger = logging.getLogger(__name__)

def is_permanent_media_url(url: str) -> bool:
    """
    Return True when an image URL points to COL Realty's configured
    permanent media storage.

    Production uses the configured S3 bucket. Local development may
    use Django's MEDIA_URL.
    """
    if not url:
        return False

    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)

    if bucket_name:
        return bucket_name in url

    media_url = getattr(settings, "MEDIA_URL", "/media/")
    return bool(media_url and url.startswith(media_url))


def get_latest_mls_modification_timestamp() -> Optional[str]:
    """
    Return the greatest MLS ModificationTimestamp currently stored
    in the Listing table as an ISO8601 UTC string.

    MLS Grid incremental replication uses:
        ModificationTimestamp gt <latest stored timestamp>
    """
    agg = Listing.objects.aggregate(
        max_ts=Max("mls_modification_timestamp")
    )

    ts = agg["max_ts"]

    if not ts:
        return None

    ts = ts.astimezone(timezone.utc).replace(microsecond=0)

    return ts.isoformat().replace("+00:00", "Z")


def sync_mls_listings(updated_since: Optional[str] = None) -> int:
    """
    Fetch MLS Grid listing changes and upsert them into Listing.

    Image downloading is intentionally NOT performed here.

    Media URLs received in the incremental MLS Grid record are stored with
    the listing for later processing by the separate cache_images command.

    Existing permanent image URLs are preserved individually so an MLS sync
    does not overwrite cached images with temporary MLS Grid URLs.
    """
    client = MLSClient()

    if updated_since is None:
        updated_since = get_latest_mls_modification_timestamp()

    if updated_since is None:
        logger.info(
            "No existing MLS data; performing initial MLS Grid import."
        )
    else:
        logger.info(
            "MLS Grid incremental sync starting from "
            "ModificationTimestamp > %s",
            updated_since,
        )

    count = 0
    created_count = 0
    updated_count = 0
    error_count = 0

    for record in client.iter_properties(updated_since=updated_since):
        try:
            data = map_property_to_listing_data(record)

            mls_id = data.pop("mls_id", None)

            if not mls_id:
                logger.warning(
                    "Skipping MLS record without ListingKey: %s",
                    record,
                )
                continue

            # Preserve permanent S3 images already cached for this listing.
            #
            # Each image is preserved independently because the MLS main
            # image may still be rate-limited while secondary photos have
            # already been successfully cached in S3.
            existing = Listing.objects.filter(
                mls_id=mls_id
            ).first()

            if existing:

                existing_main_image = existing.main_image_url or ""

                # Preserve the true main image if it is already cached.
                if is_permanent_media_url(existing_main_image):
                    data["main_image_url"] = existing_main_image

                # Preserve each cached image by its original MLS position.
                # Uncached positions keep the fresh MLS Grid URL supplied
                # by the current sync.
                existing_images = existing.image_urls or []
                incoming_images = data.get("image_urls") or []

                if existing_images and incoming_images:
                    merged_images = list(incoming_images)

                    for index, existing_url in enumerate(existing_images):
                        if (
                            is_permanent_media_url(existing_url)
                            and index < len(merged_images)
                        ):
                            merged_images[index] = existing_url

                    data["image_urls"] = merged_images

            # Upsert the MLS record.
            with transaction.atomic():
                listing, created = Listing.objects.update_or_create(
                    mls_id=mls_id,
                    defaults=data,
                )

            if created:
                created_count += 1
            else:
                updated_count += 1

            count += 1

            # Visible progress during manual runs.
            if count % 500 == 0:
                print(
                    f"Processed {count}: "
                    f"created={created_count}, "
                    f"updated={updated_count}, "
                    f"errors={error_count}",
                    flush=True,
                )

                logger.info(
                    "MLS sync progress: processed=%s created=%s "
                    "updated=%s errors=%s",
                    count,
                    created_count,
                    updated_count,
                    error_count,
                )

        except Exception:
            error_count += 1

            logger.exception(
                "Error processing MLS record ListingKey=%s",
                record.get("ListingKey"),
            )

            continue

    logger.info(
        "MLS Grid sync complete. processed=%s created=%s "
        "updated=%s errors=%s",
        count,
        created_count,
        updated_count,
        error_count,
    )

    print(
        f"MLS sync complete: processed={count}, "
        f"created={created_count}, "
        f"updated={updated_count}, "
        f"errors={error_count}",
        flush=True,
    )

    return count
