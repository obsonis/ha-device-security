"""Diagnostics for Device Security."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from . import DeviceSecurityConfigEntry
from .registry import build_devices

TO_REDACT = {CONF_API_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DeviceSecurityConfigEntry
) -> dict[str, Any]:
    """Config (token redacted), last registry post and the current summary."""
    coordinator = entry.runtime_data.coordinator
    devices = build_devices(hass)

    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "registry": {
            "devices_in_registry": len(devices),
            "devices_with_mac": sum(
                1 for d in devices if any(c[0] == "mac" for c in d["connections"])
            ),
            "devices_behind_hub": sum(1 for d in devices if d["via_device_id"]),
            "last_sync": coordinator.last_registry_sync.isoformat()
            if coordinator.last_registry_sync
            else None,
            "last_sync_devices": coordinator.last_registry_devices,
            "last_error": coordinator.last_registry_error,
        },
        "summary": coordinator.data,
    }
