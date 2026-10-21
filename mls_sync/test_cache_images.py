from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from listings.models import Listing


@override_settings(AWS_STORAGE_BUCKET_NAME="test-colrealty-media")
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
                "https://test-colrealty-media.s3.amazonaws.com/"
                "listings/TEST-CACHE-001/photo_000.jpg"
            ),
            (
                "https://test-colrealty-media.s3.amazonaws.com/"
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
            "https://test-colrealty-media.s3.amazonaws.com/"
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
                "https://test-colrealty-media.s3.amazonaws.com/"
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

    @patch("mls_sync.management.commands.cache_images.default_storage.exists", return_value=False)
    @patch("mls_sync.management.commands.cache_images.cache_primary_photo")
    @patch("mls_sync.management.commands.cache_images.MLSClient")
    def test_refresh_media_recovers_one_listing(self, mock_client, mock_cache, mock_exists):
        permanent_url = (
            "https://test-colrealty-media.s3.amazonaws.com/"
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
            "https://test-colrealty-media.s3.amazonaws.com/"
            "listings/TEST-CACHE-001/photo_000.jpg"
        )
        mock_url.return_value = permanent_url

        call_command("cache_images", refresh_media=True, mls_id="TEST-CACHE-001")

        mock_client.assert_not_called()
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.main_image_url, permanent_url)
        self.assertEqual(self.listing.image_urls, self.source_urls)
