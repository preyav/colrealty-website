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
        mock_listing.objects.filter.return_value.order_by.return_value.count.return_value = 1
        mock_listing.objects.filter.return_value.order_by.return_value.iterator.return_value = [
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

        mock_listing.objects.filter.return_value.order_by.return_value.count.return_value = 1
        mock_listing.objects.filter.return_value.order_by.return_value.iterator.return_value = [
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

class RentalMigrationBatchTests(SimpleTestCase):
    """Exercise command batching without touching a database."""

    def make_query(self, mock_listing, listings):
        query = mock_listing.objects.filter.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        query.count.return_value = len(listings)
        query.iterator.side_effect = lambda: iter(listings)
        return query

    @patch("rentals.management.commands.migrate_leases.Rental")
    @patch("rentals.management.commands.migrate_leases.Listing")
    @patch("rentals.management.commands.migrate_leases.sync_values")
    def test_limit_counts_actionable_updates_not_unchanged_records(
        self, mock_sync, mock_listing, mock_rental
    ):
        listings = [SimpleNamespace(mls_id=f"TEST{i}") for i in range(6)]
        self.make_query(mock_listing, listings)
        mock_rental.objects.filter.return_value.first.return_value = MagicMock()
        mock_sync.side_effect = [{}, {"price": 101}, {}, {"price": 103}]
        output = StringIO()

        call_command("migrate_leases", "--update", "--limit", "2", stdout=output)

        self.assertEqual(mock_sync.call_count, 4)
        self.assertIn("Would update existing: 2", output.getvalue())
        self.assertIn("Skipped (unchanged or --update not specified): 2", output.getvalue())
        mock_rental.objects.create.assert_not_called()

    @patch("rentals.management.commands.migrate_leases.Rental")
    @patch("rentals.management.commands.migrate_leases.Listing")
    def test_mls_id_filters_to_requested_listing(self, mock_listing, mock_rental):
        listing = SimpleNamespace(mls_id="ACT123", status="active", price=2100)
        query = self.make_query(mock_listing, [listing])
        mock_rental.objects.filter.return_value.first.return_value = None
        output = StringIO()

        with patch(
            "rentals.management.commands.migrate_leases.FIELDS_TO_SYNC", ["price"]
        ):
            call_command(
                "migrate_leases", "--mls-id", "ACT123", "--commit", stdout=output
            )

        mock_listing.objects.filter.assert_called_once_with(
            property_type__in=["Residential Lease", "Commercial Lease"]
        )
        query.filter.assert_called_once_with(mls_id="ACT123")
        mock_rental.objects.create.assert_called_once_with(
            price=2100, mls_id="ACT123", status="active"
        )
        self.assertIn("Migrated new: 1", output.getvalue())

    @patch("rentals.management.commands.migrate_leases.Rental")
    @patch("rentals.management.commands.migrate_leases.Listing")
    @patch("rentals.management.commands.migrate_leases.sync_values")
    def test_repeated_committed_batches_advance(
        self, mock_sync, mock_listing, mock_rental
    ):
        listings = [SimpleNamespace(mls_id=f"TEST{i}") for i in range(4)]
        self.make_query(mock_listing, listings)
        records = {listing.mls_id: MagicMock(price=0) for listing in listings}
        current = {"mls_id": None}

        def rental_filter(**kwargs):
            current["mls_id"] = kwargs["mls_id"]
            result = MagicMock()
            result.first.return_value = records[current["mls_id"]]
            return result

        mock_rental.objects.filter.side_effect = rental_filter

        def changes(listing, existing):
            return {"price": 2500} if existing.price != 2500 else {}

        mock_sync.side_effect = changes
        first = StringIO()
        second = StringIO()
        call_command(
            "migrate_leases", "--update", "--commit", "--limit", "2", stdout=first
        )
        call_command(
            "migrate_leases", "--update", "--commit", "--limit", "2", stdout=second
        )

        self.assertEqual([record.price for record in records.values()], [2500] * 4)
        self.assertEqual(sum(record.save.call_count for record in records.values()), 4)
        self.assertIn("Updated existing: 2", first.getvalue())
        self.assertIn("Updated existing: 2", second.getvalue())
        self.assertIn("Skipped (unchanged or --update not specified): 2", second.getvalue())

    @patch("rentals.management.commands.migrate_leases.Listing")
    def test_invalid_limit_is_rejected_before_query(self, mock_listing):
        from django.core.management.base import CommandError

        for value in ("0", "-1"):
            with self.subTest(limit=value):
                with self.assertRaisesMessage(CommandError, "positive integer"):
                    call_command("migrate_leases", "--limit", value)
        mock_listing.objects.filter.assert_not_called()

    @patch("rentals.management.commands.migrate_leases.Rental")
    @patch("rentals.management.commands.migrate_leases.Listing")
    @patch("rentals.management.commands.migrate_leases.sync_values")
    def test_failed_write_does_not_consume_batch_slot(
        self, mock_sync, mock_listing, mock_rental
    ):
        listings = [SimpleNamespace(mls_id=f"TEST{i}") for i in range(3)]
        self.make_query(mock_listing, listings)
        records = [MagicMock() for _ in listings]
        records[0].save.side_effect = RuntimeError("simulated write failure")
        mock_rental.objects.filter.return_value.first.side_effect = records
        mock_sync.return_value = {"price": 2500}
        output = StringIO()

        call_command(
            "migrate_leases", "--update", "--commit", "--limit", "2", stdout=output
        )

        self.assertEqual(records[0].save.call_count, 1)
        self.assertEqual(records[1].save.call_count, 1)
        self.assertEqual(records[2].save.call_count, 1)
        self.assertIn("Updated existing: 2", output.getvalue())
        self.assertIn("Errors: 1", output.getvalue())

    @patch("rentals.management.commands.migrate_leases.Rental")
    @patch("rentals.management.commands.migrate_leases.Listing")
    def test_existing_only_skips_missing_rentals(
        self, mock_listing, mock_rental
    ):
        listings = [SimpleNamespace(mls_id=f"TEST{i}") for i in range(3)]
        self.make_query(mock_listing, listings)
        mock_rental.objects.filter.return_value.first.return_value = None
        output = StringIO()

        call_command(
            "migrate_leases",
            "--update",
            "--existing-only",
            "--commit",
            stdout=output,
        )

        mock_rental.objects.create.assert_not_called()
        self.assertIn("Migrated new: 0", output.getvalue())
        self.assertIn(
            "Skipped (unchanged or --update not specified): 3",
            output.getvalue(),
        )

    @patch("rentals.management.commands.migrate_leases.Rental")
    @patch("rentals.management.commands.migrate_leases.Listing")
    @patch("rentals.management.commands.migrate_leases.sync_values")
    def test_existing_only_updates_existing_rentals(
        self, mock_sync, mock_listing, mock_rental
    ):
        listings = [SimpleNamespace(mls_id="TEST1")]
        self.make_query(mock_listing, listings)

        existing = MagicMock()
        mock_rental.objects.filter.return_value.first.return_value = existing
        mock_sync.return_value = {"status": "inactive"}
        output = StringIO()

        call_command(
            "migrate_leases",
            "--update",
            "--existing-only",
            "--commit",
            stdout=output,
        )

        self.assertEqual(existing.status, "inactive")
        existing.save.assert_called_once_with(update_fields=["status"])
        mock_rental.objects.create.assert_not_called()
        self.assertIn("Updated existing: 1", output.getvalue())