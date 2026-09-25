"""Build the device registry payload posted to the platform."""

from __future__ import annotations

from collections import defaultdict
import logging
from pathlib import Path
from typing import Any

from homeassistant.components import network
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    instance_id,
)

from .const import MAX_CONNECTIONS, MAX_DEVICES, MAX_DOMAINS, MAX_STRING

_LOGGER = logging.getLogger(__name__)


def _text(value: Any) -> str | None:
    """A string field as the platform accepts it: trimmed, capped, None when empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text[:MAX_STRING] or None


def _integration(hass: HomeAssistant, device: dr.DeviceEntry) -> str | None:
    """The domain of the config entry that owns the device."""
    entry_id = getattr(device, "primary_config_entry", None)
    if entry_id is None and device.config_entries:
        entry_id = next(iter(device.config_entries))
    if entry_id is None:
        return None
    entry = hass.config_entries.async_get_entry(entry_id)
    return entry.domain if entry else None


def build_devices(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Every device registry entry, with its entity domains.

    The platform reads manufacturer, model, firmware and the "mac" connection to
    match devices it scans, and via_device_id to place Zigbee / Z-Wave /
    Matter devices behind their hub.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    domains: dict[str, set[str]] = defaultdict(set)
    for entity in entity_registry.entities.values():
        if entity.device_id:
            domains[entity.device_id].add(entity.domain)

    devices: list[dict[str, Any]] = []
    for device in device_registry.devices.values():
        if len(devices) >= MAX_DEVICES:
            _LOGGER.warning(
                "Device registry has more than %s devices; the rest are not sent",
                MAX_DEVICES,
            )
            break

        connections = [
            [_text(kind), _text(value)]
            for kind, value in sorted(device.connections)
            if _text(kind) and _text(value)
        ][:MAX_CONNECTIONS]

        devices.append(
            {
                "id": device.id,
                "via_device_id": device.via_device_id,
                "integration": _text(_integration(hass, device)),
                "manufacturer": _text(device.manufacturer),
                "model": _text(device.model),
                "model_id": _text(getattr(device, "model_id", None)),
                "sw_version": _text(device.sw_version),
                "hw_version": _text(device.hw_version),
                "name": _text(device.name),
                "name_by_user": _text(device.name_by_user),
                "entry_type": device.entry_type.value if device.entry_type else None,
                "connections": connections,
                "entity_domains": sorted(domains.get(device.id, set()))[:MAX_DOMAINS],
            }
        )

    return devices


def _read_mac(interface: str) -> str | None:
    """The interface's MAC from sysfs (Linux only; None elsewhere)."""
    try:
        mac = Path(f"/sys/class/net/{interface}/address").read_text().strip()
    except OSError:
        return None
    return mac if mac and mac != "00:00:00:00:00:00" else None


async def async_host_addresses(hass: HomeAssistant) -> dict[str, list[str]]:
    """MAC and IPv4 addresses of this host's enabled network adapters.

    The platform places devices on the Home Assistant host's own radio (a USB
    Zigbee coordinator, a Thread border router) under the host's device, which
    it finds by these addresses.
    """
    macs: list[str] = []
    ips: list[str] = []

    try:
        adapters = await network.async_get_adapters(hass)
    except Exception:  # noqa: BLE001 - host addresses are optional
        _LOGGER.debug("Could not read network adapters", exc_info=True)
        return {"mac_addresses": macs, "ip_addresses": ips}

    for adapter in adapters:
        if not adapter.get("enabled"):
            continue
        for ipv4 in adapter.get("ipv4", []):
            address = ipv4.get("address")
            if address and address not in ips:
                ips.append(address)
        name = adapter.get("name")
        if name:
            mac = await hass.async_add_executor_job(_read_mac, name)
            if mac and mac not in macs:
                macs.append(mac)

    return {"mac_addresses": macs[:16], "ip_addresses": ips[:16]}


async def async_build_payload(hass: HomeAssistant) -> dict[str, Any]:
    """The full registry post."""
    return {
        "instance_id": await instance_id.async_get(hass),
        "ha_version": HA_VERSION,
        "host": await async_host_addresses(hass),
        "devices": build_devices(hass),
    }
