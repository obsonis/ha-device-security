"""Coordinator: summary polling and device registry posting."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DeviceSecurityApiClient, DeviceSecurityAuthError, DeviceSecurityError
from .const import DOMAIN, SUMMARY_INTERVAL
from .registry import async_build_payload

_LOGGER = logging.getLogger(__name__)


class DeviceSecurityCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the platform summary and posts the device registry.

    The summary is the coordinator's data (sensors). The registry post runs on
    its own schedule (see __init__.py) and records its outcome here for
    diagnostics.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: DeviceSecurityApiClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SUMMARY_INTERVAL,
        )
        self.client = client
        self.last_registry_sync: datetime | None = None
        self.last_registry_devices: int | None = None
        self.last_registry_error: str | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_get_summary()
        except DeviceSecurityAuthError as err:
            raise ConfigEntryAuthFailed("The platform refused the API token") from err
        except DeviceSecurityError as err:
            raise UpdateFailed(f"Error reading the platform summary: {err}") from err

    async def async_sync_registry(self, _now: datetime | None = None) -> None:
        """Post the device registry. Failures are logged, never raised."""
        payload = await async_build_payload(self.hass)

        try:
            await self.client.async_post_registry(payload)
        except DeviceSecurityAuthError:
            self.last_registry_error = "auth"
            if self.config_entry is not None:
                self.config_entry.async_start_reauth(self.hass)
            return
        except DeviceSecurityError as err:
            self.last_registry_error = str(err)
            _LOGGER.warning(
                "Could not send the device registry to the platform: %s", err
            )
            return

        self.last_registry_sync = dt_util.utcnow()
        self.last_registry_devices = len(payload["devices"])
        self.last_registry_error = None
        _LOGGER.debug("Sent %s devices to the platform", self.last_registry_devices)
