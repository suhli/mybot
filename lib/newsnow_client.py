from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class NewsNowError(Exception):
    """Base exception for NewsNow client errors."""


class NewsNowHTTPError(NewsNowError):
    """Raised when NewsNow returns non-2xx responses."""


@dataclass(slots=True)
class NewsNowClient:
    """Simple synchronous client for NewsNow public APIs."""

    base_url: str = "https://newsnow.busiyi.world"
    timeout: float = 15.0

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "NewsNowClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def get_latest_version(self) -> str:
        """
        GET /api/latest
        Returns:
            version string from response field `v`.
        """
        data = self._request("GET", "/api/latest")
        version = data.get("v")
        if not isinstance(version, str) or not version:
            raise NewsNowError("Invalid response from /api/latest: missing field 'v'")
        return version

    def get_source(self, source_id: str, latest: bool | str | None = None) -> dict[str, Any]:
        """
        GET /api/s?id=<source_id>[&latest=true]
        Args:
            source_id: News source id, e.g. 'hackernews'.
            latest: Optional. True/'true' means prefer newer data.
        """
        if not source_id:
            raise ValueError("source_id must not be empty")

        params: dict[str, Any] = {"id": source_id}
        if latest is not None:
            params["latest"] = latest
        return self._request("GET", "/api/s", params=params)

    def get_entire(self, sources: list[str]) -> list[dict[str, Any]]:
        """
        POST /api/s/entire
        Args:
            sources: list of source ids.
        """
        if not sources:
            raise ValueError("sources must not be empty")
        payload = {"sources": sources}
        data = self._request("POST", "/api/s/entire", json=payload)
        if not isinstance(data, list):
            raise NewsNowError("Invalid response from /api/s/entire: expected a list")
        return data

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = self._client.request(method, path, params=params, json=json)
        except httpx.HTTPError as exc:
            raise NewsNowError(f"Request failed: {exc}") from exc

        if response.status_code >= 400:
            raise NewsNowHTTPError(
                f"HTTP {response.status_code} for {method} {path}: {response.text}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise NewsNowError(f"Invalid JSON response for {method} {path}") from exc

