from django.core.management.base import BaseCommand
from mls_sync.services import sync_mls_listings
from mls_sync.client import MLSClientError


class Command(BaseCommand):
    help = "Sync listings from MLS Grid (ACTRIS) into the local Listing model."

    def add_arguments(self, parser):
        parser.add_argument(
            "--updated-since",
            type=str,
            default=None,
            help="Override ModificationTimestamp filter (ISO8601, UTC). "
                 "If omitted, uses greatest mls_modification_timestamp from DB or initial import.",
        )

    def handle(self, *args, **options):
        updated_since = options["updated_since"]
        try:
            count = sync_mls_listings(updated_since=updated_since)
        except MLSClientError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        self.stdout.write(self.style.SUCCESS(f"Synced {count} listings from MLS Grid."))