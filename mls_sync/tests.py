from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase, override_settings

from listings.models import Listing
from mls_sync.services import sync_mls_listings


class MLSImagePipelineTests(TestCase):
    def _record(self, listing_key="TEST-MLS-001", status="Active"):
        return {
            "ListingKey": listing_key,
            "ModificationTimestamp": datetime.now(timezone.utc).isoformat(),
            "StandardStatus": status,
            "PropertyType": "Residential",
            "PropertySubType": "Single Family Residence",
            "StreetNumber": "100",
            "StreetName": "Test",
            "City": "Austin",
            "StateOrProvince": "TX",
            "PostalCode": "78701",
            "ListPrice": 500000,
            "Media": [
                {
                    "Order": 0,
                    "MediaURL": "https://example.test/photo1.jpg",
                },
                {
                    "Order": 1,
                    "MediaURL": "https://example.test/photo2.jpg",
                },
            ],
        }

    @patch("mls_sync.services.MLSClient")
    def test_sync_stores_media_urls_without_downloading_images(
        self,
        mock_client_class,
    ):
        mock_client_class.return_value.iter_properties.return_value = [
            self._record()
        ]

        sync_mls_listings(
            updated_since="2026-01-01T00:00:00Z"
        )

        listing = Listing.objects.get(
            mls_id="TEST-MLS-001"
        )

        self.assertEqual(
            listing.image_urls,
            [
                "https://example.test/photo1.jpg",
                "https://example.test/photo2.jpg",
            ],
        )

        self.assertEqual(
            listing.main_image_url,
            "https://example.test/photo1.jpg",
        )

    @override_settings(
        AWS_STORAGE_BUCKET_NAME="test-colrealty-media"
    )
    @patch("mls_sync.services.MLSClient")
    def test_sync_preserves_existing_permanent_images(
        self,
        mock_client_class,
    ):
        permanent_main = (
            "https://test-colrealty-media.s3.amazonaws.com/"
            "listings/TEST-MLS-002/photo_000.jpg"
        )

        permanent_second = (
            "https://test-colrealty-media.s3.amazonaws.com/"
            "listings/TEST-MLS-002/photo_001.jpg"
        )

        Listing.objects.create(
            mls_id="TEST-MLS-002",
            title="Existing listing",
            status="active",
            price=500000,
            main_image_url=permanent_main,
            image_urls=[
                permanent_main,
                permanent_second,
            ],
        )

        mock_client_class.return_value.iter_properties.return_value = [
            self._record("TEST-MLS-002")
        ]

        sync_mls_listings(
            updated_since="2026-01-01T00:00:00Z"
        )

        listing = Listing.objects.get(
            mls_id="TEST-MLS-002"
        )

        self.assertEqual(
            listing.main_image_url,
            permanent_main,
        )

        self.assertEqual(
            listing.image_urls,
            [
                permanent_main,
                permanent_second,
            ],
        )

    @patch("mls_sync.services.MLSClient")
    def test_sync_stores_inactive_listing_without_image_download(
        self,
        mock_client_class,
    ):
        mock_client_class.return_value.iter_properties.return_value = [
            self._record(
                "TEST-MLS-003",
                status="Expired",
            )
        ]

        sync_mls_listings(
            updated_since="2026-01-01T00:00:00Z"
        )

        self.assertTrue(
            Listing.objects.filter(
                mls_id="TEST-MLS-003"
            ).exists()
        )
