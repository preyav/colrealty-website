"""
Management command to migrate lease listings from Listing → Rental model.

Usage:
    python manage.py migrate_leases                    # dry run
    python manage.py migrate_leases --commit           # migrate new only
    python manage.py migrate_leases --update           # dry run update existing
    python manage.py migrate_leases --update --commit  # update existing + migrate new
"""

from django.core.management.base import BaseCommand
from listings.models import Listing
from rentals.models import Rental

LEASE_TYPES = ["Residential Lease", "Commercial Lease"]

FIELDS_TO_SYNC = [
    "mls_modification_timestamp", "title", "street_address", "city", "state",
    "zip_code", "county", "subdivision", "price", "hoa_fee", "hoa_frequency",
    "buyer_agent_compensation", "beds", "baths", "baths_full", "baths_half",
    "sqft", "lot_size", "lot_size_sqft", "property_type", "year_built",
    "stories", "garage_spaces", "parking_total", "interior_features",
    "exterior_features", "community_features", "parking_features", "appliances",
    "flooring", "laundry_features", "window_features", "patio_porch_features",
    "has_fireplace", "has_pool", "has_garage", "is_waterfront", "is_new_construction",
    "construction_materials", "foundation", "roof", "fencing", "direction_faces",
    "heating", "cooling", "sewer", "water_source", "school_district",
    "elementary_school", "middle_school", "high_school", "open_house_date",
    "open_house_start_time", "open_house_end_time", "listing_agent_name",
    "listing_agent_email", "listing_agent_phone", "listing_office_name",
    "main_image_url", "image_urls", "virtual_tour_url", "days_on_market",
    "description", "directions", "latitude", "longitude", "is_featured",
]


class Command(BaseCommand):
    help = "Migrate lease listings from Listing model to Rental model"

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Actually perform the migration (default is dry run)",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Also update existing Rental records with latest data from Listing",
        )

    def handle(self, *args, **options):
        commit = options["commit"]
        update = options["update"]
        qs = Listing.objects.filter(property_type__in=LEASE_TYPES)
        total = qs.count()

        self.stdout.write(f"Found {total} lease listings in Listing model")
        if not commit:
            self.stdout.write("DRY RUN — pass --commit to actually run")

        migrated = 0
        updated = 0
        skipped = 0
        errors = 0

        for listing in qs.iterator():
            try:
                existing = Rental.objects.filter(mls_id=listing.mls_id).first()

                if existing:
                    if update:
                        for field in FIELDS_TO_SYNC:
                            setattr(existing, field, getattr(listing, field))
                        existing.status = listing.status if listing.status in ["active", "inactive"] else "inactive"
                        if commit:
                            existing.save()
                        updated += 1
                    else:
                        skipped += 1
                    continue

                if commit:
                    kwargs = {field: getattr(listing, field) for field in FIELDS_TO_SYNC}
                    kwargs["mls_id"] = listing.mls_id
                    kwargs["status"] = listing.status if listing.status in ["active", "inactive"] else "inactive"
                    Rental.objects.create(**kwargs)

                migrated += 1

                if (migrated + updated) % 500 == 0:
                    self.stdout.write(f"  Progress: migrated={migrated} updated={updated} / {total}")

            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(f"  Error on {listing.mls_id}: {e}"))

        self.stdout.write("=" * 50)
        self.stdout.write(f"{'Migrated' if commit else 'Would migrate'} new: {migrated}")
        self.stdout.write(f"{'Updated' if commit else 'Would update'} existing: {updated}")
        self.stdout.write(f"Skipped (no --update flag): {skipped}")
        self.stdout.write(f"Errors: {errors}")

        if commit:
            self.stdout.write(self.style.SUCCESS(
                f"\n✅ Done! {migrated} new + {updated} updated in Rental model."
            ))
