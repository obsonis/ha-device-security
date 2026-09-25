"""Client for the platform's Home Assistant API."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import REGISTRY_PATH, REQUEST_TIMEOUT, SUMMARY_PATH


class DeviceSecurityError(Exception):
    """Base error talking to the platform."""


class DeviceSecurityAuthError(DeviceSecurityError):
    """The token was refused (401) or lacks the home-assistant ability (403)."""


class DeviceSecurityConnectionError(DeviceSecurityError):
    """The platform could not be reached or answered unexpectedly."""


class DeviceSecurityApiClient:
    """Posts the device registry and reads the risk summary.

    Only outbound calls from Home Assistant to the platform: the platform never holds a
    Home Assistant token.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        token: str,
        tenant: str | None = None,
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._token = token
        self._tenant = tenant

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        if self._tenant:
            headers["X-Tenant"] = self._tenant
        return headers

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.request(
                    method,
                    f"{self._url}{path}",
                    json=payload,
                    headers=self._headers(),
                )
        except (TimeoutError, aiohttp.ClientError) as err:
            raise DeviceSecurityConnectionError(str(err)) from err

        async with response:
            if response.status in (401, 403):
                raise DeviceSecurityAuthError(f"HTTP {response.status}")
            if response.status >= 400:
                raise DeviceSecurityConnectionError(f"HTTP {response.status}")
            try:
                data = await response.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError) as err:
                raise DeviceSecurityConnectionError("Invalid JSON response") from err

        if not isinstance(data, dict):
            raise DeviceSecurityConnectionError("Unexpected response")
        return data

    async def async_get_summary(self) -> dict[str, Any]:
        """Return the summary's data object."""
        data = await self._request("GET", SUMMARY_PATH)
        summary = data.get("data")
        if not isinstance(summary, dict):
            raise DeviceSecurityConnectionError("Summary missing data")
        return summary

    async def async_post_registry(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Post the device registry; the platform queues it and answers 202."""
        return await self._request("POST", REGISTRY_PATH, payload)
