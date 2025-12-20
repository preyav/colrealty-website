import random
from django.core.management.base import BaseCommand
from listings.models import Listing

class Command(BaseCommand):
    help = "Create sample 'fake IDX' listings for development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=20,
            help="Number of sample listings to create (default: 20)",
        )

    def handle(self, *args, **options):
        count = options["count"]

        cities = [
            ("Austin", "TX"),
            ("Round Rock", "TX"),
            ("Pflugerville", "TX"),
            ("Cedar Park", "TX"),
            ("Leander", "TX"),
            ("Georgetown", "TX"),
        ]

        street_names = [
            "Barton Springs Rd",
            "South Congress Ave",
            "Guadalupe St",
            "Lamar Blvd",
            "Burnet Rd",
            "Parmer Ln",
            "Mopac Expy",
            "Ranch Rd 620",
            "Anderson Mill Rd",
            "Chisholm Trail",
        ]

        property_types = [
            "Single Family",
            "Condo",
            "Townhome",
            "Duplex",
            "Multi-Family",
        ]

        statuses = ["active", "pending", "sold"]
        base_lat = 30.2672
        base_lng = -97.7431

        created = 0

        for _ in range(count):
            city, state = random.choice(cities)
            street_number = random.randint(200, 9900)
            street = random.choice(street_names)
            zip_code = random.choice(["78701", "78702", "78704", "78745", "78664", "78681"])

            beds = random.choice([2, 3, 3, 4, 4, 5])
            baths = random.choice([1.0, 2.0, 2.5, 3.0])
            sqft = random.randint(900, 3500)
            lot_size = round(random.uniform(0.1, 0.4), 2)
            year_built = random.randint(1985, 2023)
            price = random.randint(275000, 950000)
            property_type = random.choice(property_types)
            status = random.choice(statuses)

            lat = base_lat + random.uniform(-0.15, 0.15)
            lng = base_lng + random.uniform(-0.15, 0.15)

            mls_id = f"CR-{city[:2].upper()}-{random.randint(100000, 999999)}"

            listing, created_flag = Listing.objects.get_or_create(
                mls_id=mls_id,
                defaults={
                    "title": f"{beds} BR {property_type} in {city}",
                    "street_address": f"{street_number} {street}",
                    "city": city,
                    "state": state,
                    "zip_code": zip_code,
                    "price": price,
                    "beds": beds,
                    "baths": baths,
                    "sqft": sqft,
                    "lot_size": lot_size,
                    "property_type": property_type,
                    "year_built": year_built,
                    "status": status,
                    "latitude": lat,
                    "longitude": lng,
                    "main_image_url": "",
                    "is_featured": random.random() < 0.25,
                },
            )

            if created_flag:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} sample listing(s)."))
