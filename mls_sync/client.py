# mls_sync/client.py
import logging
from typing import Dict, Any, Iterable, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MLSClientError(Exception):
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
