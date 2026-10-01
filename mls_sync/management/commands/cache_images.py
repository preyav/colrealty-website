"""
mls_sync/management/commands/cache_images.py

Caches MLS images permanently using Media URLs already stored in the
Listing/Rental database records.

IMPORTANT:
This command does NOT scan the MLS Grid Property feed. The normal
incremental MLS sync is responsible for receiving Media URLs and storing
them in image_urls. This command processes a small, bounded database
backlog and copies those images into permanent storage.

Run manually:
    python manage.py cache_images
    python manage.py cache_images --mls-id ACT220365592
    python manage.py cache_images --limit 10
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from listings.models import Listing
from rentals.models import Rental
from mls_sync.image_cache import cache_listing_photos


logger = logging.getLogger(__name__)

NOT_FOUND_FILE = Path("logs/cache_images_not_found.json")
NOT_FOUND_COOLDOWN_DAYS = 7

MAIN_IMAGE_COOLDOWN_FILE = Path("logs/cache_images_main_cooldown.json")
MAIN_IMAGE_COOLDOWN_HOURS = 12

DEFAULT_LIMIT = 10


def is_permanent_media_url(url):
    """
    Return True when a URL points to COL Realty's configured
    permanent media storage.
    """
    if not url:
        return False

    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)

    if bucket_name:
        return bucket_name in url

    media_url = getattr(settings, "MEDIA_URL", "/media/")
    return bool(media_url and url.startswith(media_url))


def load_not_found_cache():
    if not NOT_FOUND_FILE.exists():
        return {}

    try:
        with NOT_FOUND_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_not_found_cache(data):
    NOT_FOUND_FILE.parent.mkdir(parents=True, exist_ok=True)

    with NOT_FOUND_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def load_main_image_cooldown():
    if not MAIN_IMAGE_COOLDOWN_FILE.exists():
        return {}

    try:
        with MAIN_IMAGE_COOLDOWN_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_main_image_cooldown(data):
    MAIN_IMAGE_COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)

    with MAIN_IMAGE_COOLDOWN_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


class Command(BaseCommand):
    help = (
        "Cache MLS images permanently using Media URLs already stored "
        "in Listing/Rental records"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--mls-id",
            type=str,
            help="Cache images for a single record by MLS ID",
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_LIMIT,
            help=(
                "Max number of records to process in one run "
                f"(default: {DEFAULT_LIMIT})"
            ),
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help=(
                "Allow active records even when their main image is "
                "already permanently cached"
            ),
        )

        parser.add_argument(
            "--rentals",
            action="store_true",
            help="Process Rental model instead of Listing model",
        )

    def handle(self, *args, **options):
        mls_id = options.get("mls_id")
        limit = options.get("limit")
        process_all = options.get("all")
        use_rentals = options.get("rentals")

        if limit is None or limit < 1:
            raise CommandError("--limit must be at least 1.")

        Model = Rental if use_rentals else Listing
        model_name = "Rental" if use_rentals else "Listing"

        self.stdout.write(
            self.style.NOTICE(
                f"=== Col Realty Image Cacher [{model_name}] ==="
            )
        )

        self.stdout.write(
            "Source: image URLs already stored in PostgreSQL. "
            "No MLS Property-feed scan will be performed."
        )

        # -------------------------------------------------------------
        # Build candidate queryset.
        # -------------------------------------------------------------
        if mls_id:
            qs = Model.objects.filter(mls_id=mls_id)

            self.stdout.write(
                f"Targeting single {model_name}: {mls_id}"
            )

        elif process_all:
            qs = Model.objects.filter(status="active")

            self.stdout.write(
                f"Processing active {model_name} records..."
            )

        else:
            # We intentionally avoid hard-coding the S3 bucket into the
            # database query. Permanent-storage detection is performed
            # below using Django's configured storage settings.
            qs = Model.objects.filter(status="active")

            self.stdout.write(
                f"Looking for active {model_name} records "
                f"without a permanent main image..."
            )

        # Only retain records that actually need image work unless
        # --all or a specific --mls-id was requested.
        if not process_all and not mls_id:
            candidate_ids = []

            for record in qs.only(
                "mls_id",
                "main_image_url",
            ).iterator(chunk_size=500):
                if not is_permanent_media_url(
                    record.main_image_url or ""
                ):
                    candidate_ids.append(record.mls_id)

            qs = Model.objects.filter(
                mls_id__in=candidate_ids
            )

        total_before_cooldown = qs.count()

        self.stdout.write(
            f"Found {total_before_cooldown} "
            f"{model_name} records before cooldown filtering. "
            f"Limit: {limit}"
        )

        # -------------------------------------------------------------
        # Load no-image cooldown.
        #
        # In the old implementation this represented records not found
        # while scanning MLS. We now use it for records that currently
        # have no usable image URLs stored in PostgreSQL.
        # -------------------------------------------------------------
        not_found_cache = load_not_found_cache()

        cooldown_cutoff = (
            datetime.now(timezone.utc)
            - timedelta(days=NOT_FOUND_COOLDOWN_DAYS)
        )

        cooldown_ids = []

        for mid, timestamp in not_found_cache.items():
            try:
                failed_at = datetime.fromisoformat(timestamp)

                if failed_at >= cooldown_cutoff:
                    cooldown_ids.append(mid)

            except (TypeError, ValueError):
                continue

        # A manually requested --mls-id always bypasses cooldown.
        if cooldown_ids and not mls_id:
            qs = qs.exclude(mls_id__in=cooldown_ids)

            self.stdout.write(
                f"Skipping {len(cooldown_ids)} MLS IDs still within "
                f"{NOT_FOUND_COOLDOWN_DAYS}-day no-image cooldown."
            )

        # -------------------------------------------------------------
        # Load main-image retry cooldown.
        # -------------------------------------------------------------
        main_image_cooldown = load_main_image_cooldown()

        main_cooldown_cutoff = (
            datetime.now(timezone.utc)
            - timedelta(hours=MAIN_IMAGE_COOLDOWN_HOURS)
        )

        main_cooldown_ids = []

        for mid, timestamp in main_image_cooldown.items():
            try:
                failed_at = datetime.fromisoformat(timestamp)

                if failed_at >= main_cooldown_cutoff:
                    main_cooldown_ids.append(mid)

            except (TypeError, ValueError):
                continue

        if main_cooldown_ids and not mls_id:
            qs = qs.exclude(mls_id__in=main_cooldown_ids)

            self.stdout.write(
                f"Skipping {len(main_cooldown_ids)} MLS IDs still within "
                f"{MAIN_IMAGE_COOLDOWN_HOURS}-hour main-image cooldown."
            )

        total = qs.count()

        self.stdout.write(
            f"Eligible after cooldown: "
            f"{total} {model_name} records."
        )

        if total == 0:
            self.stdout.write(
                self.style.SUCCESS("Nothing to do!")
            )
            return

        # -------------------------------------------------------------
        # Select a strictly bounded batch.
        #
        # Listings:
        #   1. newest records from the last 24 hours
        #   2. oldest backlog records with remaining capacity
        #
        # This keeps new inventory fresh while steadily shrinking the
        # historical backlog.
        # -------------------------------------------------------------
        if not use_rentals and not mls_id:
            recent_cutoff = (
                datetime.now(timezone.utc)
                - timedelta(hours=24)
            )

            recent_ids = list(
                qs.filter(
                    created_at__gte=recent_cutoff
                )
                .order_by("-created_at")
                .values_list(
                    "mls_id",
                    flat=True,
                )[:limit]
            )

            remaining_slots = max(
                0,
                limit - len(recent_ids),
            )

            backlog_ids = []

            if remaining_slots:
                backlog_ids = list(
                    qs.exclude(
                        mls_id__in=recent_ids
                    )
                    .order_by("created_at")
                    .values_list(
                        "mls_id",
                        flat=True,
                    )[:remaining_slots]
                )

            selected_ids = recent_ids + backlog_ids

            self.stdout.write(
                f"Selected {len(recent_ids)} recent "
                f"and {len(backlog_ids)} backlog listings."
            )

        else:
            selected_ids = list(
                qs.order_by("created_at")
                .values_list(
                    "mls_id",
                    flat=True,
                )[:limit]
            )

        if not selected_ids:
            self.stdout.write(
                self.style.SUCCESS("Nothing selected.")
            )
            return

        # Fetch only the selected rows from PostgreSQL.
        records_by_id = {
            record.mls_id: record
            for record in Model.objects.filter(
                mls_id__in=selected_ids
            )
        }

        processed = 0
        success = 0
        skipped = 0
        no_stored_images = 0

        self.stdout.write(
            f"Processing {len(selected_ids)} database-selected "
            f"{model_name} records..."
        )

        # -------------------------------------------------------------
        # Cache using URLs already stored in PostgreSQL.
        #
        # There is deliberately NO MLSClient here and NO Property API
        # traversal.
        # -------------------------------------------------------------
        for listing_key in selected_ids:
            record = records_by_id.get(listing_key)

            if record is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {listing_key}: database record disappeared; "
                        f"skipping"
                    )
                )

                skipped += 1
                processed += 1
                continue

            stored_urls = list(
                record.image_urls or []
            )

            # Keep only usable strings and preserve their MLS order.
            image_urls = [
                url.strip()
                for url in stored_urls
                if isinstance(url, str) and url.strip()
            ]

            # If image_urls is empty but main_image_url contains a
            # temporary source URL, retain it as a last-resort source.
            if (
                not image_urls
                and record.main_image_url
                and not is_permanent_media_url(
                    record.main_image_url
                )
            ):
                image_urls = [
                    record.main_image_url
                ]

            if not image_urls:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {listing_key}: no image URLs stored "
                        f"in PostgreSQL; skipping"
                    )
                )

                not_found_cache[listing_key] = (
                    datetime.now(timezone.utc).isoformat()
                )

                save_not_found_cache(
                    not_found_cache
                )

                no_stored_images += 1
                skipped += 1
                processed += 1
                continue

            self.stdout.write(
                f"  {listing_key}: "
                f"caching {len(image_urls)} stored images..."
            )

            try:
                main_url, cached_urls = (
                    cache_listing_photos(
                        listing_key,
                        image_urls,
                    )
                )

                Model.objects.filter(
                    mls_id=listing_key
                ).update(
                    main_image_url=main_url,
                    image_urls=cached_urls,
                )

                cached_count = sum(
                    1
                    for url in cached_urls
                    if is_permanent_media_url(url)
                )

                main_cached = (
                    is_permanent_media_url(main_url)
                )

                if main_cached:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✓ {listing_key}: "
                            f"cached {cached_count}/"
                            f"{len(image_urls)} images"
                        )
                    )

                    success += 1

                    # Clear stale cooldown entries after success.
                    cooldown_changed = False

                    if listing_key in not_found_cache:
                        not_found_cache.pop(
                            listing_key,
                            None,
                        )
                        save_not_found_cache(
                            not_found_cache
                        )
                        cooldown_changed = True

                    if listing_key in main_image_cooldown:
                        main_image_cooldown.pop(
                            listing_key,
                            None,
                        )
                        save_main_image_cooldown(
                            main_image_cooldown
                        )
                        cooldown_changed = True

                    if cooldown_changed:
                        logger.info(
                            "Cleared image cooldown for %s",
                            listing_key,
                        )

                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠ {listing_key}: "
                            f"cached {cached_count}/"
                            f"{len(image_urls)} images; "
                            f"main image NOT cached"
                        )
                    )

                    # If all secondary images are cached and only the
                    # main image remains, avoid repeatedly consuming a
                    # processing slot.
                    secondary_count = max(
                        0,
                        len(image_urls) - 1,
                    )

                    if cached_count >= secondary_count:
                        main_image_cooldown[listing_key] = (
                            datetime.now(
                                timezone.utc
                            ).isoformat()
                        )

                        save_main_image_cooldown(
                            main_image_cooldown
                        )

                        self.stdout.write(
                            f"  Main image retry deferred for "
                            f"{MAIN_IMAGE_COOLDOWN_HOURS} hours."
                        )

                    skipped += 1

            except Exception as exc:
                logger.exception(
                    "Image caching failed for %s",
                    listing_key,
                )

                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ {listing_key}: "
                        f"error — {exc}"
                    )
                )

                skipped += 1

            processed += 1

            if processed % 10 == 0:
                self.stdout.write(
                    f"  Progress: "
                    f"{processed}/{len(selected_ids)}"
                )

        # -------------------------------------------------------------
        # Summary.
        # -------------------------------------------------------------
        self.stdout.write(
            "\n" + "=" * 40
        )

        self.stdout.write(
            self.style.SUCCESS("Done!")
        )

        self.stdout.write(
            f"  Processed        : {processed}"
        )

        self.stdout.write(
            f"  Cached           : {success}"
        )

        self.stdout.write(
            f"  Skipped          : {skipped}"
        )

        self.stdout.write(
            f"  No stored images : {no_stored_images}"
        )

        self.stdout.write(
            "  MLS feed scans   : 0"
        )
