import random
import string
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone


def _rand_str(n=8):
    return "".join(random.choices(string.ascii_letters, k=n))


class Command(BaseCommand):
    help = "Seed the database with sample Listing records (for local/dev)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=20, help="Number of listings to create (default: 20)")
        parser.add_argument("--clear", action="store_true", help="Delete existing listings before seeding")
        parser.add_argument(
            "--status",
            type=str,
            default="active",
            help="Status value to use if the Listing model has a 'status' field (default: active)",
        )
        parser.add_argument("--force-images", action="store_true", help="Set placeholder image URL on existing rows missing it")


    def handle(self, *args, **options):
        count = options["count"]
        clear = options["clear"]
        status_value = options["status"]

        # Import here so Django app registry is ready
        from listings.models import Listing  # noqa

        if clear:
            deleted, _ = Listing.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared existing listings (deleted: {deleted})."))

        fields = {f.name: f for f in Listing._meta.get_fields() if getattr(f, "concrete", False)}

        def has(name: str) -> bool:
            return name in fields

        # Only set values for fields that exist.
        # This makes it resilient if you rename fields later.
        created = 0

        for i in range(1, count + 1):
            obj = Listing()

            # Common fields
            if has("title"):
                obj.title = f"Sample Listing {i} — {_rand_str(5)}"

            if has("description"):
                obj.description = "Sample listing generated for local development."

            if has("status"):
                obj.status = status_value

            # Address-ish fields
            if has("street_address"):
                obj.street_address = f"{100 + i} Main St"
            if has("address") and not getattr(obj, "address", None):
                obj.address = f"{100 + i} Main St"
            if has("city"):
                obj.city = random.choice(["Austin", "Round Rock", "Cedar Park", "Leander"])
            if has("state"):
                obj.state = "TX"
            if has("zip_code"):
                obj.zip_code = random.choice(["78701", "78704", "78613", "78641"])

            # Numeric fields
            if has("price"):
                # handle DecimalField / IntegerField
                base = Decimal("350000")
                obj.price = base + Decimal(i * 10000)

            if has("beds"):
                obj.beds = random.randint(2, 5)

            if has("baths"):
                # some models use Decimal for baths
                obj.baths = Decimal(str(round(random.uniform(1.0, 4.0), 1)))

            if has("sqft"):
                obj.sqft = random.randint(900, 4200)

            if has("lot_size"):
                obj.lot_size = Decimal(str(round(random.uniform(0.10, 0.75), 2)))

            if has("year_built"):
                obj.year_built = random.randint(1975, 2022)

            if has("property_type"):
                obj.property_type = random.choice(["Single Family", "Condo", "Townhome", "Multi-Family"])

            # Geo + images
            if has("latitude"):
                obj.latitude = Decimal("30.2672") + Decimal(str(random.uniform(-0.10, 0.10)))
            if has("longitude"):
                obj.longitude = Decimal("-97.7431") + Decimal(str(random.uniform(-0.10, 0.10)))

            if has("main_image_url"):
                # placeholder image URL
                obj.main_image_url = "https://placehold.co/1200x800?text=ColRealty+Listing"

            if has("is_featured"):
                obj.is_featured = (i % 6 == 0)

            # Timestamps (only if you have them & they aren't auto-managed)
            if has("created_at") and not fields["created_at"].auto_now_add:
                obj.created_at = timezone.now()
            if has("updated_at") and not fields["updated_at"].auto_now:
                obj.updated_at = timezone.now()

            # MLS fields (optional)
            if has("mls_id"):
                obj.mls_id = f"MLS-{100000 + i}"
            if has("mls_modification_timestamp"):
                obj.mls_modification_timestamp = timezone.now()

            # Save
            obj.save()
            created += 1
        if options["force_images"] and "main_image_url" in [f.name for f in Listing._meta.fields]:
            Listing.objects.filter(main_image_url="").update(
                main_image_url="https://placehold.co/1200x800?text=ColRealty+Listing"
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} Listing record(s)."))
