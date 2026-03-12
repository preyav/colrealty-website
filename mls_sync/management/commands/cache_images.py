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

import time
import logging
from django.core.management.base import BaseCommand
from django.db.models import Q
from listings.models import Listing
from rentals.models import Rental
from mls_sync.client import MLSClient
from mls_sync.image_cache import cache_listing_photos

logger = logging.getLogger(__name__)


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

        self.stdout.write(self.style.NOTICE(f"=== Col Realty Image Cacher [{model_name}] ==="))

        # ── Build queryset ─────────────────────────────────────────────
        if mls_id:
            qs = Model.objects.filter(mls_id=mls_id)
            self.stdout.write(f"Targeting single {model_name}: {mls_id}")
        elif process_all:
            qs = Model.objects.filter(status="active")
            self.stdout.write(f"Processing ALL active {model_name} records...")
        else:
            # Only records with non-S3 main image URLs
            qs = Model.objects.filter(status="active").exclude(
                main_image_url__startswith="https://colrealty-media.s3"
            )
            self.stdout.write(f"Processing {model_name} records with non-S3 images...")

        total = qs.count()
        self.stdout.write(f"Found {total} {model_name} records to process. Limit: {limit}")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to do!"))
            return

        qs = qs[:limit]

        # ── Fetch fresh URLs from MLS and cache ───────────────────────
        client = MLSClient()
        processed = 0
        success = 0
        skipped = 0
        api_calls = 0

        target_ids = set(qs.values_list("mls_id", flat=True))
        self.stdout.write(f"Fetching fresh URLs from MLS API for {len(target_ids)} records...")

        for record in client.iter_properties(updated_since="2020-01-01T00:00:00Z"):
            listing_key = record.get("ListingKey") or record.get("ListingId", "")
            api_calls += 1

            if listing_key not in target_ids:
                continue

            media = record.get("Media") or []
            image_urls = [m["MediaURL"] for m in sorted(media, key=lambda x: x.get("Order", 0)) if m.get("MediaURL")]

            if not image_urls:
                self.stdout.write(f"  {listing_key}: no images in MLS, skipping")
                skipped += 1
                target_ids.discard(listing_key)
                processed += 1
            else:
                self.stdout.write(f"  {listing_key}: caching {len(image_urls)} images...")
                try:
                    main_url, cached_urls = cache_listing_photos(listing_key, image_urls)
                    Model.objects.filter(mls_id=listing_key).update(
                        main_image_url=main_url,
                        image_urls=cached_urls,
                    )
                    self.stdout.write(self.style.SUCCESS(f"  ✓ {listing_key}: cached {len(cached_urls)} images"))
                    success += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ✗ {listing_key}: error — {e}"))
                    skipped += 1

                target_ids.discard(listing_key)
                processed += 1

            if processed % 10 == 0:
                self.stdout.write(f"  Progress: {processed}/{min(total, limit)} | API calls: {api_calls}")

            if not target_ids:
                break

            time.sleep(0.5)

        # ── Summary ───────────────────────────────────────────────────
        self.stdout.write("\n" + "="*40)
        self.stdout.write(self.style.SUCCESS("Done!"))
        self.stdout.write(f"  Processed : {processed}")
        self.stdout.write(f"  Cached    : {success}")
        self.stdout.write(f"  Skipped   : {skipped}")
        self.stdout.write(f"  Not found : {len(target_ids)}")
        self.stdout.write(f"  API calls : {api_calls}")

        if target_ids:
            self.stdout.write(f"\nNot found in MLS (may be expired/removed):")
            for mid in list(target_ids)[:10]:
                self.stdout.write(f"  - {mid}")
