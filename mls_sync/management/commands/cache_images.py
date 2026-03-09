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
from mls_sync.client import MLSClient
from mls_sync.mappers import map_property_to_listing_data
from mls_sync.image_cache import cache_listing_photos

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Cache MLS images permanently for listings with missing or expired images"

    def add_arguments(self, parser):
        parser.add_argument(
            "--mls-id",
            type=str,
            help="Cache images for a single listing by MLS ID (e.g. ACT220365592)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Max number of listings to process in one run (default: 200)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Process ALL listings, not just those missing images",
        )

    def handle(self, *args, **options):
        mls_id = options.get("mls_id")
        limit = options.get("limit")
        process_all = options.get("all")

        self.stdout.write(self.style.NOTICE("=== Col Realty Image Cacher ==="))

        # ── Build queryset ─────────────────────────────────────────────
        if mls_id:
            qs = Listing.objects.filter(mls_id=mls_id)
            self.stdout.write(f"Targeting single listing: {mls_id}")
        elif process_all:
            qs = Listing.objects.filter(status="active")
            self.stdout.write(f"Processing ALL active listings...")
        else:
            # Only listings with missing main image
            qs = Listing.objects.filter(
                status="active"
            ).filter(
                Q(main_image_url="") | Q(main_image_url__isnull=True)
            )
            self.stdout.write(f"Processing listings with missing images...")

        total = qs.count()
        self.stdout.write(f"Found {total} listings to process. Limit: {limit}")

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

        # Build a lookup dict of mls_id -> listing for efficient matching
        target_ids = set(qs.values_list("mls_id", flat=True))
        self.stdout.write(f"Fetching fresh URLs from MLS API for {len(target_ids)} listings...")

        for record in client.iter_properties(updated_since="2020-01-01T00:00:00Z"):
            listing_key = record.get("ListingKey") or record.get("ListingId", "")
            api_calls += 1

            if listing_key not in target_ids:
                continue

            # Found a match — get fresh image URLs
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
                    Listing.objects.filter(mls_id=listing_key).update(
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

            # Progress update every 10 listings
            if processed % 10 == 0:
                self.stdout.write(f"  Progress: {processed}/{min(total, limit)} | API calls: {api_calls}")

            # Stop when all targets found
            if not target_ids:
                break

            # Respect MLS rate limits — pause between listings
            time.sleep(0.5)

        # ── Summary ───────────────────────────────────────────────────
        self.stdout.write("\n" + "="*40)
        self.stdout.write(self.style.SUCCESS(f"Done!"))
        self.stdout.write(f"  Processed : {processed}")
        self.stdout.write(f"  Cached    : {success}")
        self.stdout.write(f"  Skipped   : {skipped}")
        self.stdout.write(f"  Not found : {len(target_ids)}")
        self.stdout.write(f"  API calls : {api_calls}")

        if target_ids:
            self.stdout.write(f"\nListings not found in MLS (may be expired/removed):")
            for mid in list(target_ids)[:10]:
                self.stdout.write(f"  - {mid}")
