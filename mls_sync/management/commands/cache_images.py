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

from common.media_storage import media_storage_key
from listings.models import Listing
from rentals.models import Rental
from mls_sync.image_cache import cache_primary_photo, PrimaryImageRateLimitError, PrimaryImageBatchStopError
from mls_sync.client import MLSClient, MLSClientError, MLSRateLimitError, MLSBatchStopError
from django.core.files.storage import default_storage
from mls_sync.image_cache import _get_cache_path


logger = logging.getLogger(__name__)

NOT_FOUND_FILE = Path("logs/cache_images_not_found.json")
NOT_FOUND_COOLDOWN_DAYS = 7

MAIN_IMAGE_COOLDOWN_FILE = Path("logs/cache_images_main_cooldown.json")
MAIN_IMAGE_COOLDOWN_HOURS = 12

DEFAULT_LIMIT = 10


def is_permanent_media_url(url):
    """Identify references belonging to configured public media storage."""
    return media_storage_key(url) is not None


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
            "--refresh-media",
            action="store_true",
            help="Fetch fresh primary Media for exactly one --mls-id (no bulk scan)",
        )
        parser.add_argument(
            "--refresh-batch",
            action="store_true",
            help="Recover missing primary images in a bounded batch (max 10)",
        )
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

    def _refresh_one(self, mls_id, use_rentals):
        """Opt-in single-ID recovery; no feed traversal or gallery mutation."""
        Model = Rental if use_rentals else Listing
        record = Model.objects.filter(mls_id=mls_id).first()
        if record is None:
            raise CommandError(f"No local record found for MLS ID {mls_id}")

        # Do not touch records whose existing permanent main photo is usable.
        existing = record.main_image_url or ""
        storage_key = media_storage_key(existing)
        if storage_key and default_storage.exists(storage_key):
            self.stdout.write(self.style.SUCCESS(
                f"{mls_id}: permanent primary image exists; skipping"
            ))
            return

        # S3 may already contain a photo even if the DB points to an expired URL.
        # Avoid an MLS request when an existing primary photo can be reused.
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            path = f"listings/{mls_id}/photo_000{ext}"
            if default_storage.exists(path):
                Model.objects.filter(pk=record.pk).update(
                    main_image_url=default_storage.url(path)
                )
                self.stdout.write(self.style.SUCCESS(
                    f"{mls_id}: reused existing primary image"
                ))
                return

        # Respect existing recovery cooldowns before contacting MLS Grid.
        now = datetime.now(timezone.utc)

        for cache, duration, label in (
            (load_main_image_cooldown(), timedelta(hours=MAIN_IMAGE_COOLDOWN_HOURS), "main-image"),
            (load_not_found_cache(), timedelta(days=NOT_FOUND_COOLDOWN_DAYS), "not-found"),
        ):
            timestamp = cache.get(mls_id)
            if not timestamp:
                continue
            try:
                recorded = datetime.fromisoformat(timestamp)
                if recorded.tzinfo is None:
                    recorded = recorded.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue

            if recorded + duration > now:
                self.stdout.write(self.style.WARNING(
                    f"{mls_id}: {label} cooldown active until "
                    f"{(recorded + duration).isoformat()}; skipping"
                ))
                return

        try:
            media = MLSClient().get_property_media(mls_id)
        except (MLSRateLimitError, MLSBatchStopError) as exc:
            cooldown = load_main_image_cooldown()
            cooldown[mls_id] = now.isoformat()
            save_main_image_cooldown(cooldown)
            raise CommandError(f"MLS recovery stopped: {exc}") from exc
        except MLSClientError as exc:
            cooldown = load_main_image_cooldown()
            cooldown[mls_id] = now.isoformat()
            save_main_image_cooldown(cooldown)
            raise CommandError(str(exc)) from exc
        urls = []
        for item in media:
            if not isinstance(item, dict):
                continue
            url = item.get("MediaURL") or item.get("MediaURLLarge") or item.get("MediaURLMedium")
            if isinstance(url, str) and url.strip():
                urls.append(url.strip())
        if not urls:
            cooldown = load_not_found_cache()
            cooldown[mls_id] = now.isoformat()
            save_not_found_cache(cooldown)
            self.stdout.write(self.style.WARNING(
                f"{mls_id}: MLS Grid returned no photo URL; unchanged"
            ))
            return

        try:
            cached_url = cache_primary_photo(mls_id, urls[0])
        except (PrimaryImageRateLimitError, PrimaryImageBatchStopError) as exc:
            cooldown = load_main_image_cooldown()
            cooldown[mls_id] = now.isoformat()
            save_main_image_cooldown(cooldown)
            raise CommandError(f"MLS image caching stopped: {exc}") from exc
        except Exception:
            cooldown = load_main_image_cooldown()
            cooldown[mls_id] = now.isoformat()
            save_main_image_cooldown(cooldown)
            raise

        if not cached_url or not is_permanent_media_url(cached_url):
            cooldown = load_main_image_cooldown()
            cooldown[mls_id] = now.isoformat()
            save_main_image_cooldown(cooldown)
            self.stdout.write(self.style.WARNING(
                f"{mls_id}: primary photo could not be cached; unchanged"
            ))
            return
        Model.objects.filter(pk=record.pk).update(main_image_url=cached_url)
        self.stdout.write(self.style.SUCCESS(
            f"{mls_id}: primary image recovered; gallery preserved"
        ))


    def _refresh_batch(self, limit, use_rentals):
        """Recover at most ten primary images without scanning the MLS feed."""
        import time

        Model = Rental if use_rentals else Listing
        model_name = "Rental" if use_rentals else "Listing"

        now = datetime.now(timezone.utc)
        main_cooldown = load_main_image_cooldown()
        not_found = load_not_found_cache()

        def cooling_down(cache, mls_id, duration):
            timestamp = cache.get(mls_id)
            if not timestamp:
                return False
            try:
                failed_at = datetime.fromisoformat(timestamp)
                if failed_at.tzinfo is None:
                    failed_at = failed_at.replace(tzinfo=timezone.utc)
                return failed_at >= now - duration
            except (TypeError, ValueError):
                return False

        self.stdout.write(
            f"=== Bounded MLS Primary Image Recovery [{model_name}] ==="
        )

        # Query local active records only. No MLS Property-feed traversal.
        qs = (
            Model.objects.filter(status="active")
            .exclude(mls_id__isnull=True)
            .exclude(mls_id="")
            .order_by("created_at", "pk")
        )

        # Keep database traversal bounded as well as API requests.
        scan_limit = min(100, max(20, limit * 10))
        candidates = list(qs[:scan_limit])

        selected = []

        for record in candidates:
            mls_id = record.mls_id
            current_url = record.main_image_url or ""

            # Skip records with an existing permanent primary image.
            storage_key = media_storage_key(current_url)
            if storage_key and default_storage.exists(storage_key):
                continue

            # Reuse cached S3 images even during cooldown.
            # This requires no MLS Grid API request.
            existing_path = None
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                path = f"listings/{mls_id}/photo_000{ext}"
                if default_storage.exists(path):
                    existing_path = path
                    break

            # Apply cooldown only when an MLS request may be needed.
            if not existing_path:
                if cooling_down(
                    main_cooldown,
                    mls_id,
                    timedelta(hours=MAIN_IMAGE_COOLDOWN_HOURS),
                ):
                    continue

                if cooling_down(
                    not_found,
                    mls_id,
                    timedelta(days=NOT_FOUND_COOLDOWN_DAYS),
                ):
                    continue

            selected.append(record)

            if len(selected) >= limit:
                break
        self.stdout.write(
            f"Selected {len(selected)} records; maximum allowed: {limit}"
        )

        recovered = 0
        reused = 0
        failed = 0
        api_requests = 0
        client = None

        for record in selected:
            mls_id = record.mls_id

            # Reuse existing permanent storage before requesting MLS data.
            existing_path = None
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                path = f"listings/{mls_id}/photo_000{ext}"
                if default_storage.exists(path):
                    existing_path = path
                    break

            if existing_path:
                permanent_url = default_storage.url(existing_path)
                Model.objects.filter(pk=record.pk).update(
                    main_image_url=permanent_url
                )
                reused += 1
                main_cooldown.pop(mls_id, None)
                not_found.pop(mls_id, None)
                save_main_image_cooldown(main_cooldown)
                save_not_found_cache(not_found)
                continue

            if cooling_down(
                main_cooldown,
                mls_id,
                timedelta(hours=MAIN_IMAGE_COOLDOWN_HOURS),
            ):
                continue

            if cooling_down(
                not_found,
                mls_id,
                timedelta(days=NOT_FOUND_COOLDOWN_DAYS),
            ):
                continue

            try:
                if client is None:
                    client = MLSClient()

                # Exactly one property-specific media lookup per record.
                api_requests += 1
                media = client.get_property_media(mls_id)

                url = next(
                    (
                        value.strip()
                        for item in media
                        if isinstance(item, dict)
                        for value in [
                            item.get("MediaURL")
                            or item.get("MediaURLLarge")
                            or item.get("MediaURLMedium")
                        ]
                        if isinstance(value, str) and value.strip()
                    ),
                    None,
                )

                if not url:
                    failed += 1
                    main_cooldown[mls_id] = now.isoformat()
                    continue

                permanent_url = cache_primary_photo(mls_id, url)

                if permanent_url and is_permanent_media_url(permanent_url):
                    Model.objects.filter(pk=record.pk).update(
                        main_image_url=permanent_url
                    )
                    recovered += 1
                    main_cooldown.pop(mls_id, None)
                    not_found.pop(mls_id, None)
                else:
                    failed += 1
                    main_cooldown[mls_id] = now.isoformat()

            except (MLSRateLimitError, MLSBatchStopError, PrimaryImageRateLimitError, PrimaryImageBatchStopError):
                self.stderr.write(
                    self.style.ERROR(
                        f"MLS access/rate-limit error: stopping batch immediately at {mls_id}"
                    )
                )
                main_cooldown[mls_id] = now.isoformat()
                break

            except MLSClientError as exc:
                failed += 1
                main_cooldown[mls_id] = now.isoformat()
                self.stderr.write(
                    f"{mls_id}: MLS media lookup failed: {exc}"
                )

            except Exception:
                failed += 1
                main_cooldown[mls_id] = now.isoformat()
                logger.exception(
                    "Batch primary-image recovery failed for %s", mls_id
                )

            finally:
                save_main_image_cooldown(main_cooldown)
                save_not_found_cache(not_found)

            # Conservative spacing between property-specific requests.
            time.sleep(2)

        self.stdout.write(
            f"Batch complete: recovered={recovered}, reused={reused}, "
            f"failed={failed}, MLS media requests={api_requests}"
        )

    def handle(self, *args, **options):
        if options.get("refresh_batch"):
            if options.get("refresh_media"):
                raise CommandError(
                    "--refresh-batch cannot be combined with --refresh-media"
                )
            if options.get("mls_id") or options.get("all"):
                raise CommandError(
                    "--refresh-batch cannot be combined with --mls-id or --all"
                )
            limit = options.get("limit")
            if limit is None or not 1 <= limit <= 10:
                raise CommandError(
                    "--refresh-batch requires --limit between 1 and 10"
                )
            return self._refresh_batch(
                limit=limit,
                use_rentals=options.get("rentals", False),
            )

        if options.get("refresh_media"):
            single_id = options.get("mls_id")
            if not single_id:
                raise CommandError("--refresh-media requires --mls-id")
            if options.get("all"):
                raise CommandError("--refresh-media cannot be combined with --all")
            return self._refresh_one(single_id, options.get("rentals", False))

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
            bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
            if bucket_name:
                # Avoid materializing tens of thousands of IDs in Python.
                qs = qs.exclude(main_image_url__contains=bucket_name)
            else:
                candidate_ids = [
                    record.mls_id
                    for record in qs.only("mls_id", "main_image_url").iterator(chunk_size=500)
                    if not is_permanent_media_url(record.main_image_url or "")
                ]
                qs = Model.objects.filter(mls_id__in=candidate_ids)

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

            # Main image only. Keep gallery URLs unchanged for future work.
            source_url = image_urls[0]
            if is_permanent_media_url(source_url):
                main_url = source_url
            else:
                main_url = None

            self.stdout.write(f"  {listing_key}: caching primary image only...")

            try:
                if main_url is None:
                    main_url = cache_primary_photo(listing_key, source_url)

                if main_url and is_permanent_media_url(main_url):
                    Model.objects.filter(mls_id=listing_key).update(
                        main_image_url=main_url,
                    )
                    success += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✓ {listing_key}: primary image cached"
                    ))
                    if listing_key in not_found_cache:
                        not_found_cache.pop(listing_key, None)
                        save_not_found_cache(not_found_cache)
                    if listing_key in main_image_cooldown:
                        main_image_cooldown.pop(listing_key, None)
                        save_main_image_cooldown(main_image_cooldown)
                else:
                    # Never replace an existing database URL on failure.
                    main_image_cooldown[listing_key] = (
                        datetime.now(timezone.utc).isoformat()
                    )
                    save_main_image_cooldown(main_image_cooldown)
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠ {listing_key}: primary image not cached"
                    ))
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
