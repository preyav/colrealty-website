from django.test import TestCase

# Create your tests here.

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from rentals.management.commands.migrate_leases import sync_values


class RentalSyncTests(SimpleTestCase):

    def make_records(self, **overrides):
        values = {
            "mls_modification_timestamp": None,
            "main_image_url": "",
            "image_urls": [],
            "status": "active",
        }
        values.update(overrides)

        listing = SimpleNamespace(**values)
        rental = SimpleNamespace(**values)
        return listing, rental

    @patch(
        "rentals.management.commands.migrate_leases.FIELDS_TO_SYNC",
        ["main_image_url", "image_urls"],
    )
    @patch(
        "rentals.management.commands.migrate_leases.media_storage_key"
    )
    def test_preserves_permanent_primary_image(self, storage_key):
        storage_key.side_effect = lambda url: (
            "photo.jpg" if url.startswith("https://storage.example/") else None
        )

        listing, rental = self.make_records()
        listing.main_image_url = "https://mls.example/temporary.jpg"
        rental.main_image_url = "https://storage.example/photo.jpg"

        changes = sync_values(listing, rental)

        self.assertNotIn("main_image_url", changes)

    @patch(
        "rentals.management.commands.migrate_leases.FIELDS_TO_SYNC",
        ["main_image_url", "image_urls"],
    )
    def test_older_listing_does_not_overwrite_rental(self):
        from datetime import datetime, timezone

        listing, rental = self.make_records()
        listing.mls_modification_timestamp = datetime(
            2026, 11, 1, tzinfo=timezone.utc
        )
        rental.mls_modification_timestamp = datetime(
            2026, 11, 15, tzinfo=timezone.utc
        )

        self.assertEqual(sync_values(listing, rental), {})

    @patch(
        "rentals.management.commands.migrate_leases.FIELDS_TO_SYNC",
        ["main_image_url", "image_urls"],
    )
    @patch(
        "rentals.management.commands.migrate_leases.media_storage_key"
    )
    def test_preserves_cached_gallery_images(self, storage_key):
        storage_key.side_effect = lambda url: (
            "photo.jpg" if url.startswith("https://storage.example/") else None
        )

        listing, rental = self.make_records()
        rental.image_urls = ["https://storage.example/photo.jpg"]
        listing.image_urls = ["https://mls.example/new-photo.jpg"]

        changes = sync_values(listing, rental)

        self.assertEqual(
            changes["image_urls"],
            [
                "https://storage.example/photo.jpg",
                "https://mls.example/new-photo.jpg",
            ],
        )

    @patch(
        "rentals.management.commands.migrate_leases.FIELDS_TO_SYNC",
        ["main_image_url", "image_urls"],
    )
    @patch(
        "rentals.management.commands.migrate_leases.media_storage_key",
        return_value=None,
    )
    def test_no_changes_for_identical_records(self, storage_key):
        listing, rental = self.make_records()
        self.assertEqual(sync_values(listing, rental), {})

    @patch(
        "rentals.management.commands.migrate_leases.FIELDS_TO_SYNC",
        ["main_image_url", "image_urls"],
    )
    def test_leased_status_is_preserved(self):
        for listing_status in ("pending", "sold"):
            with self.subTest(listing_status=listing_status):
                listing, rental = self.make_records()
                listing.status = listing_status
                rental.status = "leased"

                changes = sync_values(listing, rental)

                self.assertNotIn("status", changes)

    @patch(
        "rentals.management.commands.migrate_leases.FIELDS_TO_SYNC",
        ["main_image_url", "image_urls"],
    )
    @patch(
        "rentals.management.commands.migrate_leases.media_storage_key"
    )
    def test_image_sync_is_repeatable(self, storage_key):
        storage_key.side_effect = lambda url: (
            "photo.jpg"
            if isinstance(url, str)
            and url.startswith("https://storage.example/")
            else None
        )

        listing, rental = self.make_records()

        rental.image_urls = ["https://storage.example/photo.jpg"]
        listing.image_urls = ["https://mls.example/new-photo.jpg"]

        first_changes = sync_values(listing, rental)

        self.assertIn("image_urls", first_changes)

        rental.image_urls = first_changes["image_urls"]

        second_changes = sync_values(listing, rental)

        self.assertNotIn("image_urls", second_changes)
        
from io import StringIO
from unittest.mock import MagicMock

from django.core.management import call_command


class RentalMigrationCommandTests(SimpleTestCase):

    @patch("rentals.management.commands.migrate_leases.Rental")
    @patch("rentals.management.commands.migrate_leases.Listing")
    @patch("rentals.management.commands.migrate_leases.sync_values")
    def test_update_dry_run_does_not_save(
        self, mock_sync, mock_listing, mock_rental
    ):
        listing = MagicMock()
        listing.mls_id = "TEST123"

        existing = MagicMock()
        mock_listing.objects.filter.return_value.count.return_value = 1
        mock_listing.objects.filter.return_value.iterator.return_value = [
            listing
        ]
        mock_rental.objects.filter.return_value.first.return_value = existing

        mock_sync.return_value = {"price": 2500}

        output = StringIO()

        call_command("migrate_leases", "--update", stdout=output)

        existing.save.assert_not_called()
        mock_rental.objects.create.assert_not_called()
        self.assertIn("Would update existing: 1", output.getvalue())

    @patch("rentals.management.commands.migrate_leases.Rental")
    @patch("rentals.management.commands.migrate_leases.Listing")
    @patch("rentals.management.commands.migrate_leases.sync_values")
    def test_commit_updates_only_changed_fields(
        self, mock_sync, mock_listing, mock_rental
    ):
        listing = MagicMock()
        listing.mls_id = "TEST123"

        existing = MagicMock()

        mock_listing.objects.filter.return_value.count.return_value = 1
        mock_listing.objects.filter.return_value.iterator.return_value = [
            listing
        ]
        mock_rental.objects.filter.return_value.first.return_value = existing

        mock_sync.return_value = {"price": 2500}

        output = StringIO()

        call_command(
            "migrate_leases", "--update", "--commit", stdout=output
        )

        self.assertEqual(existing.price, 2500)
        existing.save.assert_called_once_with(update_fields=["price"])
        mock_rental.objects.create.assert_not_called()
        self.assertIn("Updated existing: 1", output.getvalue())