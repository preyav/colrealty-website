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
        "cache_listing_photos"
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

        mock_cache.return_value = (
            cached_urls[0],
            cached_urls,
        )

        call_command(
            "cache_images",
            mls_id="TEST-CACHE-001",
            limit=1,
        )

        mock_cache.assert_called_once_with(
            "TEST-CACHE-001",
            self.source_urls,
        )

        self.listing.refresh_from_db()

        self.assertEqual(
            self.listing.main_image_url,
            cached_urls[0],
        )
        self.assertEqual(
            self.listing.image_urls,
            cached_urls,
        )

    def test_cache_images_command_has_no_mls_client(self):
        from mls_sync.management.commands import cache_images

        self.assertFalse(
            hasattr(cache_images, "MLSClient"),
            "cache_images must not import or use MLSClient",
        )

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
        "cache_listing_photos"
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

        def fake_cache(mls_id, image_urls):
            permanent_url = (
                "https://test-colrealty-media.s3.amazonaws.com/"
                f"listings/{mls_id}/photo_000.jpg"
            )

            return permanent_url, [permanent_url]

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
