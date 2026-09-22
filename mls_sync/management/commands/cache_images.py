"""
mls_sync/management/commands/cache_images.py

Fetches fresh MLS image URLs and caches them permanently to storage.
Run manually:
    python manage.py cache_images
    python manage.py cache_images --mls-id ACT220365592
    python manage.py cache_images --limit 100

Add to crontab for nightly runs:
    0 2 * * * cd /home/ec2-user/colrealty && venv/bin/python manage.py cache_images --limit 500 >> logs/cache_images.log 2>&1
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.core.management.base import BaseCommand

from listings.models import Listing
from rentals.models import Rental
from mls_sync.client import MLSClient
from mls_sync.image_cache import cache_listing_photos


logger = logging.getLogger(__name__)

NOT_FOUND_FILE = Path("logs/cache_images_not_found.json")
NOT_FOUND_COOLDOWN_DAYS = 7

MAIN_IMAGE_COOLDOWN_FILE = Path("logs/cache_images_main_cooldown.json")
MAIN_IMAGE_COOLDOWN_HOURS = 12

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
    help = "Cache MLS images permanently for listings/rentals with non-S3 images"

    def add_arguments(self, parser):
        parser.add_argument(
            "--mls-id",
            type=str,
            help="Cache images for a single listing by MLS ID",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Max number of records to process in one run (default: 200)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Process ALL active records, not just those missing S3 images",
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

        Model = Rental if use_rentals else Listing
        model_name = "Rental" if use_rentals else "Listing"

        self.stdout.write(
            self.style.NOTICE(
                f"=== Col Realty Image Cacher [{model_name}] ==="
            )
        )

        # ── Build queryset ─────────────────────────────────────────────
        if mls_id:
            qs = Model.objects.filter(mls_id=mls_id)
            self.stdout.write(
                f"Targeting single {model_name}: {mls_id}"
            )

        elif process_all:
            qs = Model.objects.filter(status="active")
            self.stdout.write(
                f"Processing ALL active {model_name} records..."
            )

        else:
            qs = Model.objects.filter(status="active").exclude(
                main_image_url__startswith="https://colrealty-media.s3"
            )
            self.stdout.write(
                f"Processing {model_name} records with non-S3 images..."
            )

        total_before_cooldown = qs.count()

        self.stdout.write(
            f"Found {total_before_cooldown} "
            f"{model_name} records before cooldown filtering. "
            f"Limit: {limit}"
        )

        # ── Load not-found cooldown list ───────────────────────────────
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

        # A manually requested --mls-id should always be allowed
        if cooldown_ids and not mls_id:
            qs = qs.exclude(mls_id__in=cooldown_ids)

            self.stdout.write(
                f"Skipping {len(cooldown_ids)} MLS IDs still within "
                f"{NOT_FOUND_COOLDOWN_DAYS}-day not-found cooldown."
            )
        # Load listings whose main image recently failed to cache.
        # These are temporarily excluded so nearly-complete listings
        # do not consume the hourly cache slots repeatedly.
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

        # A manually requested --mls-id should always bypass cooldown.
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

        # ── Select records to process ─────────────────────────────────
        # For listings, prioritize records created during the last 24 hours.
        # Fill any remaining capacity with the oldest uncached listings so
        # the historical backlog continues to shrink.
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
                .values_list("mls_id", flat=True)[:limit]
            )

            remaining_slots = max(
                0,
                limit - len(recent_ids)
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
                qs.values_list(
                    "mls_id",
                    flat=True,
                )[:limit]
            )

        # ── Fetch fresh URLs from MLS and cache ───────────────────────
        client = MLSClient()

        processed = 0
        success = 0
        skipped = 0
        records_scanned = 0

        target_ids = set(selected_ids)

        self.stdout.write(
            f"Fetching fresh URLs from MLS API "
            f"for {len(target_ids)} records..."
        )

        for record in client.iter_properties(
            updated_since="2020-01-01T00:00:00Z"
        ):
            listing_key = (
                record.get("ListingKey")
                or record.get("ListingId", "")
            )

            records_scanned += 1

            if listing_key not in target_ids:
                continue

            media = record.get("Media") or []

            image_urls = [
                m["MediaURL"]
                for m in sorted(
                    media,
                    key=lambda x: x.get("Order", 0)
                )
                if m.get("MediaURL")
            ]

            if not image_urls:
                self.stdout.write(
                    f"  {listing_key}: "
                    f"no images in MLS, skipping"
                )

                skipped += 1
                target_ids.discard(listing_key)
                processed += 1

            else:
                self.stdout.write(
                    f"  {listing_key}: "
                    f"caching {len(image_urls)} images..."
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
                        if "colrealty-media.s3" in (url or "")
                    )

                    main_cached = (
                        "colrealty-media.s3" in (main_url or "")
                    )

                    if main_cached:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ {listing_key}: "
                                f"cached {cached_count}/{len(image_urls)} images"
                            )
                        )
                        success += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  ⚠ {listing_key}: "
                                f"cached {cached_count}/{len(image_urls)} images; "
                                f"main image NOT cached"
                            )
                        )

                        # If all secondary images are cached and only the main
                        # image remains, cool this listing down before retrying.
                        secondary_count = max(0, len(image_urls) - 1)

                        if cached_count >= secondary_count:
                            main_image_cooldown[listing_key] = datetime.now(
                                timezone.utc
                            ).isoformat()

                            save_main_image_cooldown(
                                main_image_cooldown
                            )

                            self.stdout.write(
                                f"  Main image retry deferred for "
                                f"{MAIN_IMAGE_COOLDOWN_HOURS} hours."
                            )

                        skipped += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ✗ {listing_key}: "
                            f"error — {e}"
                        )
                    )

                    skipped += 1

                target_ids.discard(listing_key)
                processed += 1

            if processed % 10 == 0:
                self.stdout.write(
                    f"  Progress: "
                    f"{processed}/{min(total, limit)} "
                    f"| MLS records scanned: "
                    f"{records_scanned}"
                )

            if not target_ids:
                break

        # ── Summary ───────────────────────────────────────────────────
        self.stdout.write("\n" + "=" * 40)

        self.stdout.write(
            self.style.SUCCESS("Done!")
        )

        self.stdout.write(
            f"  Processed : {processed}"
        )

        self.stdout.write(
            f"  Cached    : {success}"
        )

        self.stdout.write(
            f"  Skipped   : {skipped}"
        )

        self.stdout.write(
            f"  Not found : {len(target_ids)}"
        )

        self.stdout.write(
            f"  MLS records scanned : {records_scanned}"
        )

        # ── Record MLS IDs that were not found ────────────────────────
        if target_ids:
            self.stdout.write(
                "\nNot found in MLS "
                "(may be expired/removed):"
            )

            now_iso = datetime.now(
                timezone.utc
            ).isoformat()

            for mid in target_ids:
                not_found_cache[mid] = now_iso

            save_not_found_cache(
                not_found_cache
            )

            for mid in list(target_ids)[:10]:
                self.stdout.write(
                    f"  - {mid}"
                )

            self.stdout.write(
                f"  Added {len(target_ids)} "
                f"MLS IDs to "
                f"{NOT_FOUND_COOLDOWN_DAYS}-day cooldown."
            )