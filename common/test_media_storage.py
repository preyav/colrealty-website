from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from common.media_storage import media_storage_key, media_file_exists


class MediaStorageTests(SimpleTestCase):

    @override_settings(MEDIA_URL="/media/")
    def test_local_media_key(self):
        self.assertEqual(
            media_storage_key("/media/listings/123/photo_000.jpeg"),
            "listings/123/photo_000.jpeg",
        )

    @override_settings(MEDIA_URL="/media/")
    def test_rejects_external_url(self):
        self.assertIsNone(
            media_storage_key("https://media.mlsgrid.com/image.jpg")
        )

    @override_settings(MEDIA_URL="/media/")
    def test_rejects_unsafe_paths(self):
        for url in (
            "/media/../secret.txt",
            "/media/listings/%2e%2e/secret.txt",
            "/media/listings/%5csecret.txt",
            "/media/listings//photo.jpg",
        ):
            with self.subTest(url=url):
                self.assertIsNone(media_storage_key(url))

    @override_settings(MEDIA_URL="/media/")
    @patch("common.media_storage.default_storage.exists", return_value=True)
    def test_existing_file(self, mock_exists):
        self.assertTrue(
            media_file_exists("/media/listings/123/photo.jpg")
        )
        mock_exists.assert_called_once_with("listings/123/photo.jpg")

    @override_settings(MEDIA_URL="/media/")
    @patch("common.media_storage.default_storage.exists", return_value=False)
    def test_missing_file(self, mock_exists):
        self.assertFalse(
            media_file_exists("/media/listings/123/photo.jpg")
        )

    @override_settings(
        MEDIA_URL="https://example-bucket.s3.amazonaws.com/media/"
    )
    def test_s3_media_key(self):
        self.assertEqual(
            media_storage_key(
                "https://example-bucket.s3.amazonaws.com/media/listings/123/photo.jpg"
            ),
            "listings/123/photo.jpg",
        )
