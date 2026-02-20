from django.core.management.base import BaseCommand

from listings.models import Listing
from rentals.models import Rental


class Command(BaseCommand):
    help = "Migrate lease listings from Listing to Rental"

    def handle(self, *args, **kwargs):

        leases = Listing.objects.filter(
            property_type__in=["Residential Lease", "Commercial Lease"]
        )

        self.stdout.write(f"Found {leases.count()} lease listings")

        created = 0
        skipped = 0

        for l in leases:

            # Avoid duplicates
            if Rental.objects.filter(mls_id=l.mls_id).exists():
                skipped += 1
                continue

            Rental.objects.create(
                mls_id=l.mls_id,
                title=l.title,
                street_address=l.street_address,
                city=l.city,
                state=l.state,
                zip_code=l.zip_code,

                rent=l.price,

                beds=l.beds,
                baths=l.baths,
                sqft=l.sqft,

                property_type=l.property_type,

                latitude=l.latitude,
                longitude=l.longitude,

                main_image_url=l.main_image_url,
                description=l.description,

                status=l.status,
            )

            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created}, Skipped: {skipped}"
            )
        )
