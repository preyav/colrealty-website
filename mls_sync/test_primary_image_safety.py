
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from mls_sync.image_cache import (
    PRIMARY_MAX_BYTES,
    cache_primary_photo,
)


class PrimaryImageSafetyTests(SimpleTestCase):

    @patch("django.core.files.storage.default_storage")
    @patch("mls_sync.image_cache.requests.get")
    def test_rejects_oversized_content_length(
        self, mock_get, mock_storage
    ):
        mock_storage.exists.return_value = False

        response = MagicMock()
        response.status_code = 200
        response.headers = {
            "Content-Type": "image/jpeg",
            "Content-Length": str(PRIMARY_MAX_BYTES + 1),
        }
        mock_get.return_value.__enter__.return_value = response

        result = cache_primary_photo(
            "TEST-SAFETY-001",
            "https://media.example.test/photo.jpg",
        )

        self.assertIsNone(result)
        mock_get.assert_called_once()
        response.iter_content.assert_not_called()
        mock_storage.save.assert_not_called()

    @patch("django.core.files.storage.default_storage")
    @patch("mls_sync.image_cache.requests.get")
    def test_rejects_oversized_stream(
        self, mock_get, mock_storage
    ):
        mock_storage.exists.return_value = False

        response = MagicMock()
        response.status_code = 200
        response.headers = {"Content-Type": "image/jpeg"}
        response.iter_content.return_value = iter([
            b"x" * (PRIMARY_MAX_BYTES - 100),
            b"x" * 200,
        ])
        mock_get.return_value.__enter__.return_value = response

        result = cache_primary_photo(
            "TEST-SAFETY-002",
            "https://media.example.test/photo.jpg",
        )

        self.assertIsNone(result)
        mock_get.assert_called_once()
        mock_storage.save.assert_not_called()
