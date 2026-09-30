"""The Device Security integration.

Sends this Home Assistant's device registry (manufacturer, model, firmware,
MAC, hub) to the platform so it can match vulnerabilities, including for Zigbee,
Z-Wave and Matter devices a network scan cannot see, and shows the findings
back as sensors. All calls go out from Home Assistant; the platform never holds a
Home Assistant token.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_URL, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started

from .api import DeviceSecurityApiClient
from .const import CONF_TENANT, REGISTRY_DEBOUNCE_SECONDS, REGISTRY_INTERVAL
from .coordinator import DeviceSecurityCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class DeviceSecurityData:
    """Runtime data for a config entry."""

    client: DeviceSecurityApiClient
    coordinator: DeviceSecurityCoordinator


type DeviceSecurityConfigEntry = ConfigEntry[DeviceSecurityData]


async def async_setup_entry(
    hass: HomeAssistant, entry: DeviceSecurityConfigEntry
) -> bool:
    """Set up Device Security from a config entry."""
    client = DeviceSecurityApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data[CONF_API_TOKEN],
        entry.data.get(CONF_TENANT),
    )
    coordinator = DeviceSecurityCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = DeviceSecurityData(client=client, coordinator=coordinator)

    debouncer = Debouncer(
        hass,
        coordinator.logger,
        cooldown=REGISTRY_DEBOUNCE_SECONDS,
        immediate=False,
        function=coordinator.async_sync_registry,
    )
    entry.async_on_unload(debouncer.async_shutdown)

    @callback
    def _registry_updated(_event: Event) -> None:
        debouncer.async_schedule_call()

    entry.async_on_unload(
        hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _registry_updated)
    )
    entry.async_on_unload(
        async_track_time_interval(
            hass, coordinator.async_sync_registry, REGISTRY_INTERVAL
        )
    )

    # First post once every integration has registered its devices.
    @callback
    def _started(_hass: HomeAssistant) -> None:
        entry.async_create_background_task(
            hass, coordinator.async_sync_registry(), "device_security_registry_sync"
        )

    entry.async_on_unload(async_at_started(hass, _started))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DeviceSecurityConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
