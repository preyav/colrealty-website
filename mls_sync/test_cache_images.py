from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from listings.models import Listing
from rentals.models import Rental

@override_settings(
    AWS_STORAGE_BUCKET_NAME="test-colrealty-media",
    MEDIA_URL="https://test-colrealty-media.s3.amazonaws.com/media/",
)
class CacheImagesCommandTests(TestCase):
    def setUp(self):
        self.source_urls = [
            "https://media.example.test/photo1.jpg",
            "https://media.example.test/photo2.jpg",
        ]

        self.listing = Listing.objects.create(
            mls_id="TEST-CACHE-001",
            title="Cache command test",
            status="active",
            price=500000,
            main_image_url=self.source_urls[0],
            image_urls=self.source_urls,
        )

    @patch(
        "mls_sync.management.commands.cache_images."
        "cache_primary_photo"
    )
    def test_cache_images_uses_urls_stored_in_database(
        self,
        mock_cache,
    ):
        cached_urls = [
            (
                "https://test-colrealty-media.s3.amazonaws.com/media/"
                "listings/TEST-CACHE-001/photo_000.jpg"
            ),
            (
                "https://test-colrealty-media.s3.amazonaws.com/media/"
                "listings/TEST-CACHE-001/photo_001.jpg"
            ),
        ]

        mock_cache.return_value = cached_urls[0]

        call_command(
            "cache_images",
            mls_id="TEST-CACHE-001",
            limit=1,
        )

        mock_cache.assert_called_once_with(
            "TEST-CACHE-001",
            self.source_urls[0],
        )

        self.listing.refresh_from_db()

        self.assertEqual(
            self.listing.main_image_url,
            cached_urls[0],
        )
        self.assertEqual(
            self.listing.image_urls,
            self.source_urls,
        )

    @patch("mls_sync.management.commands.cache_images.MLSClient")
    @patch("mls_sync.management.commands.cache_images.cache_primary_photo")
    def test_normal_cache_does_not_contact_mls_grid(
        self, mock_cache, mock_mls_client
    ):
        mock_cache.return_value = (
            "https://test-colrealty-media.s3.amazonaws.com/media/"
            "listings/TEST-CACHE-001/photo_000.jpg"
        )

        call_command(
            "cache_images",
            mls_id="TEST-CACHE-001",
            limit=1,
        )

        mock_mls_client.assert_not_called()

    @patch(
        "mls_sync.management.commands.cache_images."
        "load_not_found_cache",
        return_value={},
    )
    @patch(
        "mls_sync.management.commands.cache_images."
        "load_main_image_cooldown",
        return_value={},
    )
    @patch(
        "mls_sync.management.commands.cache_images."
        "cache_primary_photo"
    )
    def test_cache_images_never_exceeds_limit(
        self,
        mock_cache,
        mock_main_cooldown,
        mock_not_found_cache,
    ):
        # setUp() already created one eligible listing.
        # Add 99 more so there are 100 eligible listings total.
        for i in range(2, 101):
            source_url = (
                f"https://media.example.test/"
                f"listing-{i}/photo1.jpg"
            )

            Listing.objects.create(
                mls_id=f"TEST-CACHE-{i:03d}",
                title=f"Cache test listing {i}",
                status="active",
                price=500000,
                main_image_url=source_url,
                image_urls=[source_url],
            )

        def fake_cache(mls_id, source_url):
            permanent_url = (
                "https://test-colrealty-media.s3.amazonaws.com/media/"
                f"listings/{mls_id}/photo_000.jpg"
            )

            return permanent_url

        mock_cache.side_effect = fake_cache

        call_command(
            "cache_images",
            limit=2,
        )

        self.assertEqual(
            mock_cache.call_count,
            2,
            "cache_images processed more listings than the configured limit",
        )

    @patch("mls_sync.management.commands.cache_images.load_not_found_cache", return_value={})
    @patch("mls_sync.management.commands.cache_images.load_main_image_cooldown", return_value={})
    @patch("mls_sync.management.commands.cache_images.default_storage.exists", return_value=False)
    @patch("mls_sync.management.commands.cache_images.cache_primary_photo")
    @patch("mls_sync.management.commands.cache_images.MLSClient")
    def test_refresh_media_recovers_one_listing(self, mock_client, mock_cache, mock_exists, mock_cooldown, mock_not_found):
        permanent_url = (
            "https://test-colrealty-media.s3.amazonaws.com/media/"
            "listings/TEST-CACHE-001/photo_000.jpg"
        )
        mock_client.return_value.get_property_media.return_value = [
            {"MediaURL": "https://media.example.test/fresh.jpg"}
        ]
        mock_cache.return_value = permanent_url

        call_command("cache_images", refresh_media=True, mls_id="TEST-CACHE-001")

        mock_client.return_value.get_property_media.assert_called_once_with("TEST-CACHE-001")
        mock_cache.assert_called_once_with(
            "TEST-CACHE-001", "https://media.example.test/fresh.jpg"
        )
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.main_image_url, permanent_url)
        self.assertEqual(self.listing.image_urls, self.source_urls)

    @patch("mls_sync.management.commands.cache_images.default_storage.exists", return_value=False)
    @patch("mls_sync.management.commands.cache_images.cache_primary_photo", return_value=None)
    @patch("mls_sync.management.commands.cache_images.MLSClient")
    def test_refresh_media_failed_download_preserves_database(self, mock_client, mock_cache, mock_exists):
        mock_client.return_value.get_property_media.return_value = [
            {"MediaURL": "https://media.example.test/fresh.jpg"}
        ]

        call_command("cache_images", refresh_media=True, mls_id="TEST-CACHE-001")

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.main_image_url, self.source_urls[0])
        self.assertEqual(self.listing.image_urls, self.source_urls)

    @patch("mls_sync.management.commands.cache_images.default_storage.url")
    @patch("mls_sync.management.commands.cache_images.default_storage.exists")
    @patch("mls_sync.management.commands.cache_images.MLSClient")
    def test_refresh_media_reuses_existing_s3_photo(self, mock_client, mock_exists, mock_url):
        mock_exists.side_effect = lambda path: path.endswith("photo_000.jpg")
        permanent_url = (
            "https://test-colrealty-media.s3.amazonaws.com/media/"
            "listings/TEST-CACHE-001/photo_000.jpg"
        )
        mock_url.return_value = permanent_url

        call_command("cache_images", refresh_media=True, mls_id="TEST-CACHE-001")

        mock_client.assert_not_called()
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.main_image_url, permanent_url)
        self.assertEqual(self.listing.image_urls, self.source_urls)

    @patch("mls_sync.management.commands.cache_images.MLSClient")
    @patch("mls_sync.management.commands.cache_images.cache_primary_photo")
    @patch(
        "mls_sync.management.commands.cache_images.load_not_found_cache",
        return_value={},
    )
    @patch(
        "mls_sync.management.commands.cache_images.load_main_image_cooldown",
        return_value={},
    )
    def test_recent_listing_and_backlog_both_selected(
        self,
        mock_main_cooldown,
        mock_not_found,
        mock_cache,
        mock_mls_client,
    ):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)

        # Existing setUp listing represents the older backlog.
        Listing.objects.filter(pk=self.listing.pk).update(
            mls_modification_timestamp=now - timedelta(days=10)
        )

        recent = Listing.objects.create(
            mls_id="TEST-RECENT-001",
            title="Recently modified listing",
            status="active",
            price=500000,
            main_image_url="https://media.example.test/recent.jpg",
            image_urls=["https://media.example.test/recent.jpg"],
        )

        Listing.objects.filter(pk=recent.pk).update(
            mls_modification_timestamp=now
        )

        processed_ids = []

        def fake_cache(mls_id, source_url):
            processed_ids.append(mls_id)
            return (
                "https://test-colrealty-media.s3.amazonaws.com/media/"
                f"listings/{mls_id}/photo_000.jpg"
            )

        mock_cache.side_effect = fake_cache

        call_command("cache_images", limit=2)

        self.assertEqual(
            processed_ids,
            ["TEST-RECENT-001", "TEST-CACHE-001"],
        )
        self.assertEqual(mock_cache.call_count, 2)
        mock_mls_client.assert_not_called()

    @patch("mls_sync.management.commands.cache_images.MLSClient")
    @patch("mls_sync.management.commands.cache_images.cache_primary_photo")
    @patch(
        "mls_sync.management.commands.cache_images.load_not_found_cache",
        return_value={},
    )
    @patch(
        "mls_sync.management.commands.cache_images.load_main_image_cooldown",
        return_value={},
    )
    def test_recent_rental_and_backlog_both_selected(
        self,
        mock_main_cooldown,
        mock_not_found,
        mock_cache,
        mock_mls_client,
    ):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)

        old_rental = Rental.objects.create(
            mls_id="TEST-RENTAL-OLD",
            title="Older rental",
            status="active",
            price=2500,
            street_address="100 Test Street",
            city="Austin",
            state="TX",
            zip_code="78717",
            main_image_url="https://media.example.test/old.jpg",
            image_urls=["https://media.example.test/old.jpg"],
        )

        recent_rental = Rental.objects.create(
            mls_id="TEST-RENTAL-RECENT",
            title="Recently modified rental",
            status="active",
            price=2600,
            street_address="200 Test Street",
            city="Austin",
            state="TX",
            zip_code="78717",
            main_image_url="https://media.example.test/recent.jpg",
            image_urls=["https://media.example.test/recent.jpg"],
        )

        Rental.objects.filter(pk=old_rental.pk).update(
            mls_modification_timestamp=now - timedelta(days=10)
        )

        Rental.objects.filter(pk=recent_rental.pk).update(
            mls_modification_timestamp=now
        )

        processed_ids = []

        def fake_cache(mls_id, source_url):
            processed_ids.append(mls_id)
            return (
                "https://test-colrealty-media.s3.amazonaws.com/media/"
                f"listings/{mls_id}/photo_000.jpg"
            )

        mock_cache.side_effect = fake_cache

        call_command("cache_images", rentals=True, limit=2)

        self.assertEqual(
            processed_ids,
            ["TEST-RENTAL-RECENT", "TEST-RENTAL-OLD"],
        )
        self.assertEqual(mock_cache.call_count, 2)
        mock_mls_client.assert_not_called()


class MLSGridRateLimitTests(TestCase):
    @override_settings(
        MLS_API_BASE_URL="https://example.test",
        MLS_API_TOKEN="test-token",
        MLS_ORIGINATING_SYSTEM_NAME="actris",
    )
    @patch("mls_sync.client.requests.get")
    def test_http_429_raises_rate_limit_error(self, mock_get):
        from mls_sync.client import MLSClient, MLSRateLimitError

        mock_get.return_value.status_code = 429

        with self.assertRaises(MLSRateLimitError):
            MLSClient().get_property_media("ACT220365592")

        mock_get.assert_called_once()


    @override_settings(
        MLS_API_BASE_URL="https://example.test/v2",
        MLS_API_TOKEN="test-token",
        MLS_ORIGINATING_SYSTEM_NAME="actris",
    )
    @patch("mls_sync.client.requests.get")
    def test_single_property_lookup_uses_targeted_filter(self, mock_get):
        from mls_sync.client import MLSClient

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "value": [{
                "ListingKey": "ACT117518432",
                "OriginatingSystemName": "actris",
                "MlgCanView": True,
                "Media": [{"MediaURL": "https://example.test/photo.jpg"}],
            }]
        }

        media = MLSClient().get_property_media("ACT117518432")

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args

        self.assertEqual(args[0], "https://example.test/v2/Property")
        self.assertIn("ListingKey eq 'ACT117518432'", kwargs["params"]["$filter"])
        self.assertIn("OriginatingSystemName eq 'actris'", kwargs["params"]["$filter"])
        self.assertEqual(kwargs["params"]["$expand"], "Media")
        self.assertEqual(kwargs["params"]["$top"], 1)
        self.assertEqual(
            media,
            [{"MediaURL": "https://example.test/photo.jpg"}],
        )


    @override_settings(
        MLS_API_BASE_URL="https://example.test/v2",
        MLS_API_TOKEN="test-token",
        MLS_ORIGINATING_SYSTEM_NAME="actris",
    )
    @patch("mls_sync.client.requests.get")
    def test_http_400_diagnostic_is_safe(self, mock_get):
        from mls_sync.client import MLSClient, MLSClientError

        mock_get.return_value.status_code = 400
        mock_get.return_value.json.return_value = {
            "error": {
                "message": "The $filter expression is unsupported",
                "details": "secret-server-detail",
            }
        }

        with self.assertRaises(MLSClientError) as caught:
            MLSClient().get_property_media("ACT117518432")

        message = str(caught.exception)

        self.assertIn("HTTP 400", message)
        self.assertIn("filter", message)
        self.assertIn("unsupported", message)
        self.assertNotIn("test-token", message)
        self.assertNotIn("secret-server-detail", message)

        mock_get.assert_called_once()


class BatchRecoverySafetyTests(TestCase):

    @override_settings(
        MEDIA_URL="https://test-colrealty-media.s3.amazonaws.com/media/"
    )
    @patch("mls_sync.management.commands.cache_images.MLSClient")
    @patch("mls_sync.management.commands.cache_images.default_storage.exists")
    def test_existing_s3_primary_is_skipped(
        self, mock_exists, mock_client
    ):
        from mls_sync.management.commands.cache_images import Command

        url = (
            "https://test-colrealty-media.s3.amazonaws.com/media/"
            "listings/TEST-S3-EXISTS/photo_000.jpg"
        )
        listing = Listing.objects.create(
            mls_id="TEST-S3-EXISTS",
            title="Existing S3 primary",
            status="active",
            price=500000,
            main_image_url=url,
            image_urls=[url],
        )

        mock_exists.return_value = True

        Command()._refresh_batch(limit=1, use_rentals=False)

        listing.refresh_from_db()
        self.assertEqual(listing.main_image_url, url)
        mock_exists.assert_any_call(
            "listings/TEST-S3-EXISTS/photo_000.jpg"
        )
        mock_client.assert_not_called()

    @override_settings(
        MEDIA_URL="https://test-colrealty-media.s3.amazonaws.com/media/"
    )
    @patch("mls_sync.management.commands.cache_images.save_not_found_cache")
    @patch("mls_sync.management.commands.cache_images.save_main_image_cooldown")
    @patch(
        "mls_sync.management.commands.cache_images.load_not_found_cache",
        return_value={},
    )
    @patch(
        "mls_sync.management.commands.cache_images.load_main_image_cooldown",
        return_value={},
    )
    @patch("mls_sync.management.commands.cache_images.MLSClient")
    @patch("mls_sync.management.commands.cache_images.default_storage.exists")
    def test_missing_s3_primary_is_eligible_for_recovery(
        self, mock_exists, mock_client, mock_main_load,
        mock_not_found_load, mock_main_save, mock_not_found_save
    ):
        from mls_sync.client import MLSRateLimitError
        from mls_sync.management.commands.cache_images import Command

        url = (
            "https://test-colrealty-media.s3.amazonaws.com/media/"
            "listings/TEST-S3-MISSING/photo_000.jpg"
        )
        listing = Listing.objects.create(
            mls_id="TEST-S3-MISSING",
            title="Missing S3 primary",
            status="active",
            price=500000,
            main_image_url=url,
            image_urls=[url],
        )

        mock_exists.return_value = False
        mock_client.return_value.get_property_media.side_effect = (
            MLSRateLimitError("HTTP 429")
        )

        Command()._refresh_batch(limit=1, use_rentals=False)

        mock_exists.assert_any_call(
            "listings/TEST-S3-MISSING/photo_000.jpg"
        )
        mock_client.return_value.get_property_media.assert_called_once_with(
            "TEST-S3-MISSING"
        )

        listing.refresh_from_db()
        self.assertEqual(listing.main_image_url, url)


    @patch("mls_sync.management.commands.cache_images.MLSClient")
    def test_refresh_batch_rejects_limit_above_ten(self, mock_client):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("cache_images", refresh_batch=True, limit=11)

        mock_client.assert_not_called()


    @patch("mls_sync.management.commands.cache_images.save_not_found_cache")
    @patch("mls_sync.management.commands.cache_images.save_main_image_cooldown")
    @patch("mls_sync.management.commands.cache_images.load_not_found_cache", return_value={})
    @patch("mls_sync.management.commands.cache_images.load_main_image_cooldown", return_value={})
    @patch("mls_sync.management.commands.cache_images.MLSClient")
    @patch("mls_sync.management.commands.cache_images.default_storage")
    def test_refresh_batch_reuses_existing_s3_photo(
        self, mock_storage, mock_client, mock_main_load,
        mock_not_found_load, mock_main_save, mock_not_found_save
    ):
        listing = Listing.objects.create(
            mls_id="TEST-BATCH-S3-001",
            title="Batch S3 reuse test",
            status="active",
            price=500000,
            main_image_url="https://expired.example.test/photo.jpg",
            image_urls=["https://expired.example.test/gallery.jpg"],
        )

        mock_storage.exists.return_value = True
        mock_storage.url.return_value = (
            "https://test-colrealty-media.s3.amazonaws.com/media/"
            "listings/TEST-BATCH-S3-001/photo_000.jpg"
        )

        from mls_sync.management.commands.cache_images import Command

        Command()._refresh_batch(limit=1, use_rentals=False)

        listing.refresh_from_db()

        self.assertIn("photo_000.jpg", listing.main_image_url)
        self.assertEqual(
            listing.image_urls,
            ["https://expired.example.test/gallery.jpg"],
        )
        mock_client.assert_not_called()


    @patch("time.sleep")
    @patch("mls_sync.management.commands.cache_images.save_not_found_cache")
    @patch("mls_sync.management.commands.cache_images.save_main_image_cooldown")
    @patch("mls_sync.management.commands.cache_images.load_not_found_cache", return_value={})
    @patch("mls_sync.management.commands.cache_images.load_main_image_cooldown", return_value={})
    @patch("mls_sync.management.commands.cache_images.default_storage")
    @patch("mls_sync.management.commands.cache_images.MLSClient")
    def test_refresh_batch_stops_on_http_429(
        self, mock_client, mock_storage, mock_main_load,
        mock_not_found_load, mock_main_save, mock_not_found_save,
        mock_sleep
    ):
        from mls_sync.client import MLSRateLimitError
        from mls_sync.management.commands.cache_images import Command

        for number in (1, 2):
            Listing.objects.create(
                mls_id=f"TEST-BATCH-429-{number}",
                title=f"Rate limit test {number}",
                status="active",
                price=500000,
                main_image_url="https://expired.example.test/photo.jpg",
                image_urls=["https://expired.example.test/gallery.jpg"],
            )

        mock_storage.exists.return_value = False
        mock_client.return_value.get_property_media.side_effect = (
            MLSRateLimitError("HTTP 429")
        )

        Command()._refresh_batch(limit=2, use_rentals=False)

        self.assertEqual(
            mock_client.return_value.get_property_media.call_count,
            1,
        )
        mock_sleep.assert_not_called()

        for number in (1, 2):
            listing = Listing.objects.get(
                mls_id=f"TEST-BATCH-429-{number}"
            )
            self.assertEqual(
                listing.main_image_url,
                "https://expired.example.test/photo.jpg",
            )


    @patch("mls_sync.management.commands.cache_images.load_not_found_cache", return_value={})
    @patch("mls_sync.management.commands.cache_images.load_main_image_cooldown")
    @patch("mls_sync.management.commands.cache_images.MLSClient")
    def test_refresh_batch_respects_main_image_cooldown(
        self, mock_client, mock_main_load, mock_not_found_load
    ):
        from datetime import datetime, timezone
        from mls_sync.management.commands.cache_images import Command

        Listing.objects.create(
            mls_id="TEST-BATCH-COOLDOWN-001",
            title="Cooldown safety test",
            status="active",
            price=500000,
            main_image_url="https://expired.example.test/photo.jpg",
            image_urls=[],
        )

        mock_main_load.return_value = {
            "TEST-BATCH-COOLDOWN-001":
                datetime.now(timezone.utc).isoformat()
        }

        Command()._refresh_batch(limit=1, use_rentals=False)

        mock_client.assert_not_called()


    @patch("mls_sync.management.commands.cache_images.save_not_found_cache")
    @patch("mls_sync.management.commands.cache_images.save_main_image_cooldown")
    @patch("mls_sync.management.commands.cache_images.load_not_found_cache", return_value={})
    @patch("mls_sync.management.commands.cache_images.load_main_image_cooldown")
    @patch("mls_sync.management.commands.cache_images.MLSClient")
    @patch("mls_sync.management.commands.cache_images.default_storage")
    def test_refresh_batch_reuses_s3_during_cooldown(
        self, mock_storage, mock_client, mock_main_load,
        mock_not_found_load, mock_main_save, mock_not_found_save
    ):
        from datetime import datetime, timezone
        from mls_sync.management.commands.cache_images import Command

        listing = Listing.objects.create(
            mls_id="TEST-BATCH-S3-COOLDOWN",
            title="S3 reuse during cooldown",
            status="active",
            price=500000,
            main_image_url="https://expired.example.test/photo.jpg",
            image_urls=[],
        )

        mock_main_load.return_value = {
            listing.mls_id: datetime.now(timezone.utc).isoformat()
        }

        mock_storage.exists.return_value = True
        mock_storage.url.return_value = (
            "https://test-colrealty-media.s3.amazonaws.com/media/"
            "listings/TEST-BATCH-S3-COOLDOWN/photo_000.jpg"
        )

        Command()._refresh_batch(limit=1, use_rentals=False)

        listing.refresh_from_db()
        self.assertIn("photo_000.jpg", listing.main_image_url)
        mock_client.assert_not_called()


    @patch("mls_sync.management.commands.cache_images.save_not_found_cache")
    @patch("mls_sync.management.commands.cache_images.save_main_image_cooldown")
    @patch("mls_sync.management.commands.cache_images.load_not_found_cache", return_value={})
    @patch("mls_sync.management.commands.cache_images.load_main_image_cooldown", return_value={})
    @patch("mls_sync.management.commands.cache_images.default_storage")
    @patch("mls_sync.management.commands.cache_images.MLSClient")
    def test_refresh_batch_stops_on_http_403_and_503(
        self, mock_client, mock_storage, mock_main_load,
        mock_not_found_load, mock_main_save, mock_not_found_save
    ):
        from mls_sync.client import MLSBatchStopError
        from mls_sync.management.commands.cache_images import Command

        for number in (1, 2):
            Listing.objects.create(
                mls_id=f"TEST-BATCH-STOP-{number}",
                title=f"HTTP stop test {number}",
                status="active",
                price=500000,
                main_image_url="https://expired.example.test/photo.jpg",
                image_urls=[],
            )

        mock_storage.exists.return_value = False

        for status in (403, 503):
            with self.subTest(status=status):
                mock_client.reset_mock()
                mock_client.return_value.get_property_media.side_effect = (
                    MLSBatchStopError(f"HTTP {status}")
                )

                Command()._refresh_batch(limit=2, use_rentals=False)

                self.assertEqual(
                    mock_client.return_value.get_property_media.call_count,
                    1,
                )

                for number in (1, 2):
                    listing = Listing.objects.get(
                        mls_id=f"TEST-BATCH-STOP-{number}"
                    )
                    self.assertEqual(
                        listing.main_image_url,
                        "https://expired.example.test/photo.jpg",
                    )

@override_settings(
    AWS_STORAGE_BUCKET_NAME="test-colrealty-media",
    MEDIA_URL="https://test-colrealty-media.s3.amazonaws.com/media/",
)
class BatchRecoveryPriorityTests(TestCase):
    """Recovery selection uses local rows and preserves MLS request limits."""

    def _create_record(self, model, mls_id, modified_at):
        fields = {
            "mls_id": mls_id,
            "title": "Recovery priority test",
            "status": "active",
            "price": 2500 if model is Rental else 500000,
            "main_image_url": "https://expired.example.test/primary.jpg",
            "image_urls": ["https://expired.example.test/gallery.jpg"],
        }
        if model is Rental:
            fields.update(
                street_address="100 Test Street",
                city="Austin",
                state="TX",
                zip_code="78717",
            )
        record = model.objects.create(**fields)
        model.objects.filter(pk=record.pk).update(
            mls_modification_timestamp=modified_at
        )
        return record

    def _run_priority_test(self, model, use_rentals):
        from datetime import datetime, timedelta, timezone
        from mls_sync.management.commands.cache_images import Command

        now = datetime.now(timezone.utc)
        prefix = "TEST-RECOVERY-RENTAL" if use_rentals else "TEST-RECOVERY-LISTING"
        # Create the old record first to catch the old created_at-only behavior.
        old = self._create_record(model, f"{prefix}-OLD", now - timedelta(days=10))
        recent = self._create_record(model, f"{prefix}-RECENT", now)
        original_gallery = list(recent.image_urls)

        with (
            patch("mls_sync.management.commands.cache_images.default_storage.exists", return_value=False),
            patch("mls_sync.management.commands.cache_images.load_main_image_cooldown", return_value={}),
            patch("mls_sync.management.commands.cache_images.load_not_found_cache", return_value={}),
            patch("mls_sync.management.commands.cache_images.save_main_image_cooldown"),
            patch("mls_sync.management.commands.cache_images.save_not_found_cache"),
            patch("mls_sync.management.commands.cache_images.MLSClient") as client,
            patch("mls_sync.management.commands.cache_images.cache_primary_photo") as cache,
            patch("time.sleep") as sleep,
        ):
            client.return_value.get_property_media.return_value = [
                {"MediaURL": "https://media.example.test/fresh.jpg"}
            ]
            cache.side_effect = lambda mls_id, url: (
                "https://test-colrealty-media.s3.amazonaws.com/media/"
                f"listings/{mls_id}/photo_000.jpg"
            )
            Command()._refresh_batch(limit=2, use_rentals=use_rentals)

            requested_ids = [
                call.args[0]
                for call in client.return_value.get_property_media.call_args_list
            ]
            self.assertEqual(requested_ids, [recent.mls_id, old.mls_id])
            self.assertEqual(client.return_value.get_property_media.call_count, 2)
            self.assertEqual(cache.call_count, 2)
            self.assertEqual(sleep.call_count, 2)

        recent.refresh_from_db()
        old.refresh_from_db()
        self.assertIn("photo_000.jpg", recent.main_image_url)
        self.assertIn("photo_000.jpg", old.main_image_url)
        self.assertEqual(recent.image_urls, original_gallery)

    def test_refresh_batch_prioritizes_recent_and_backlog_listings(self):
        self._run_priority_test(Listing, use_rentals=False)

    def test_refresh_batch_prioritizes_recent_and_backlog_rentals(self):
        self._run_priority_test(Rental, use_rentals=True)

    def test_rental_refresh_batch_stops_on_rate_limit_before_second_request(self):
        from datetime import datetime, timedelta, timezone
        from mls_sync.client import MLSRateLimitError
        from mls_sync.management.commands.cache_images import Command

        now = datetime.now(timezone.utc)
        old = self._create_record(Rental, "TEST-RECOVERY-STOP-OLD", now - timedelta(days=10))
        recent = self._create_record(Rental, "TEST-RECOVERY-STOP-RECENT", now)

        with (
            patch("mls_sync.management.commands.cache_images.default_storage.exists", return_value=False),
            patch("mls_sync.management.commands.cache_images.load_main_image_cooldown", return_value={}),
            patch("mls_sync.management.commands.cache_images.load_not_found_cache", return_value={}),
            patch("mls_sync.management.commands.cache_images.save_main_image_cooldown"),
            patch("mls_sync.management.commands.cache_images.save_not_found_cache"),
            patch("mls_sync.management.commands.cache_images.MLSClient") as client,
            patch("mls_sync.management.commands.cache_images.cache_primary_photo") as cache,
            patch("time.sleep") as sleep,
        ):
            client.return_value.get_property_media.side_effect = MLSRateLimitError("HTTP 429")
            Command()._refresh_batch(limit=2, use_rentals=True)
            client.return_value.get_property_media.assert_called_once_with(recent.mls_id)
            cache.assert_not_called()
            sleep.assert_not_called()

        for record in (old, recent):
            record.refresh_from_db()
            self.assertEqual(record.main_image_url, "https://expired.example.test/primary.jpg")
