# mls_sync/client.py
import logging
from typing import Dict, Any, Iterable, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MLSClientError(Exception):
    pass


class MLSRateLimitError(MLSClientError):
    """MLS Grid rejected a request because of rate limiting."""
    pass


class MLSBatchStopError(MLSClientError):
    """Stop batch recovery when MLS Grid denies access or is unavailable."""
    pass


class MLSClient:
    """
    Client for MLS Grid Web API (ACTRIS/ABOR).

    Follows their best-practice patterns:
    - Always filter OriginatingSystemName eq 'actris'
    - Initial import: MlgCanView eq true & $expand=Media
    - Replication: ModificationTimestamp gt [max from DB] & $expand=Media,Rooms,UnitTypes
    - Follow @odata.nextLink for paging
    """

    def __init__(self) -> None:
        self.base_url = settings.MLS_API_BASE_URL.rstrip("/")
        self.token = settings.MLS_API_TOKEN
        self.originating = settings.MLS_ORIGINATING_SYSTEM_NAME

        if not self.base_url:
            raise MLSClientError("MLS_API_BASE_URL is not configured")
        if not self.token:
            raise MLSClientError("MLS_API_TOKEN is not configured")
        if not self.originating:
            raise MLSClientError("MLS_ORIGINATING_SYSTEM_NAME is not configured")

    def _headers(self) -> Dict[str, str]:
        # Best practices say all responses are compressed; send Accept-Encoding. :contentReference[oaicite:1]{index=1}
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Accept-Encoding": "gzip,deflate",
        }

    def get_property_media(self, listing_key: str) -> list[dict]:
        """Retrieve media for one ListingKey without scanning the MLS feed."""
        if not isinstance(listing_key, str) or not listing_key.strip():
            raise MLSClientError("A nonempty ListingKey is required")

        key = listing_key.strip()
        if not key.isalnum():
            raise MLSClientError("Invalid ListingKey")

        try:
            response = requests.get(
                f"{self.base_url}/Property",
                headers=self._headers(),
                params={
                    "$filter": (
                        f"ListingKey eq '{key}' "
                        f"and OriginatingSystemName eq '{self.originating}' "
                        "and MlgCanView eq true"
                    ),
                    "$expand": "Media",
                    "$top": 1,
                },
                timeout=30,
            )
            if response.status_code == 429:
                raise MLSRateLimitError(
                    "MLS Grid rate limit reached (HTTP 429)"
                )
            if response.status_code in (403, 503):
                raise MLSBatchStopError(
                    f"MLS Grid media lookup stopped (HTTP {response.status_code})"
                )
            if response.status_code == 400:
                try:
                    payload = response.json()
                    error = payload.get("error", {}) if isinstance(payload, dict) else {}
                    if isinstance(error, dict):
                        diagnostic = str(error.get("message", ""))
                    else:
                        diagnostic = ""
                except (ValueError, TypeError):
                    diagnostic = ""

                # Report only recognized query terms, never raw API responses.
                message = diagnostic.lower()
                categories = [
                    name for name, term in (
                        ("filter", "$filter"),
                        ("top", "$top"),
                        ("expand", "$expand"),
                        ("ListingKey", "listingkey"),
                        ("syntax", "syntax"),
                        ("unsupported", "unsupported"),
                        ("invalid", "invalid"),
                        ("parameter", "parameter"),
                        ("property", "property"),
                        ("field", "field"),
                        ("query", "query"),
                        ("permission", "permission"),
                        ("forbidden", "forbidden"),
                        ("not found", "not found"),
                        ("not supported", "not supported"),
                    )
                    if term in message
                ]
                category = ", ".join(categories) if categories else "unspecified"

                logger.warning(
                    "MLS Grid targeted Property query rejected: HTTP 400 (%s)",
                    category,
                )
                raise MLSClientError(
                    f"Single-property MLS media lookup failed "
                    f"(HTTP 400; diagnostic: {category})"
                )

            response.raise_for_status()
            record = response.json()
        except (requests.RequestException, ValueError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            detail = (
                f"HTTP {status}"
                if status is not None
                else type(exc).__name__
            )
            raise MLSClientError(
                f"Single-property MLS media lookup failed ({detail})"
            ) from exc

        if not isinstance(record, dict):
            raise MLSClientError("Unexpected MLS Grid response")

        records = record.get("value")
        if not isinstance(records, list):
            raise MLSClientError("Unexpected MLS Grid Property collection")
        if len(records) != 1 or not isinstance(records[0], dict):
            raise MLSClientError("Expected exactly one MLS Grid Property")

        record = records[0]

        if str(record.get("ListingKey")) != key:
            raise MLSClientError("MLS Grid returned a different ListingKey")
        if record.get("OriginatingSystemName") != self.originating:
            raise MLSClientError("Unexpected originating system")
        if record.get("MlgCanView") is not True:
            raise MLSClientError("Property is not permitted for display")

        media = record.get("Media") or []
        if not isinstance(media, list):
            raise MLSClientError("Unexpected MLS Grid Media data")
        return media

    # ---------- PROPERTY RESOURCE ----------

    def _initial_property_url(self) -> str:
        # From best practices:
        # https://api.mlsgrid.com/v2/Property?$filter=OriginatingSystemName eq 'actris' and MlgCanView eq true&$expand=Media
        return (
            f"{self.base_url}/Property"
            f"?$filter=OriginatingSystemName eq '{self.originating}' "
            f"and MlgCanView eq true"
            f"&$expand=Media"
        )

    def _replication_property_url(self, updated_since: str) -> str:
        # From best practices:
        # ... and ModificationTimestamp gt [GREATEST ModificationTimestamp] & $expand=Media,Rooms,UnitTypes
        return (
            f"{self.base_url}/Property"
            f"?$filter=OriginatingSystemName eq '{self.originating}' "
            f"and ModificationTimestamp gt {updated_since}"
            f"&$expand=Media,Rooms,UnitTypes"
        )

    def iter_properties(
        self,
        updated_since: Optional[str] = None,
    ) -> Iterable[Dict[str, Any]]:
        """
        Yield Property records.

        - If updated_since is None → initial import (MlgCanView eq true).
        - If updated_since is provided (ISO8601) → replication since that timestamp.
        """

        if updated_since is None:
            url = self._initial_property_url()
        else:
            url = self._replication_property_url(updated_since)

        while url:
            logger.info("MLS Grid request: %s", url)
            resp = requests.get(url, headers=self._headers(), timeout=60)

            if not resp.ok:
                logger.error(
                    "MLS Grid error %s: %s", resp.status_code, resp.text[:500]
                )
                raise MLSClientError(
                    f"MLS Grid API error {resp.status_code}: {resp.text[:200]}"
                )

            data = resp.json()
            records = data.get("value") or []

            for record in records:
                yield record

            # Use @odata.nextLink exactly as recommended. :contentReference[oaicite:2]{index=2}
            url = data.get("@odata.nextLink")
