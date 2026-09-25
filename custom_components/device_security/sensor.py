"""Platform findings as sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_URL, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import DeviceSecurityConfigEntry
from .const import DOMAIN
from .coordinator import DeviceSecurityCoordinator

# Attributes stay small: Home Assistant records them on every state change.
MAX_LISTED_DEVICES = 25


def _band(data: dict[str, Any], group: str, band: str) -> int | None:
    value = (data.get(group) or {}).get(band)
    return int(value) if value is not None else None


def _last_sync(data: dict[str, Any]) -> datetime | None:
    value = (data.get("home_assistant") or {}).get("last_sync_at")
    return dt_util.parse_datetime(value) if value else None


def _devices_at_risk(data: dict[str, Any]) -> dict[str, Any]:
    devices = (data.get("home_assistant") or {}).get("devices_at_risk") or []
    return {
        "devices": [
            {
                "name": device.get("name"),
                "highest": device.get("highest"),
                "vulnerabilities": device.get("vulnerabilities"),
                "ha_device_id": device.get("ha_device_id"),
            }
            for device in devices[:MAX_LISTED_DEVICES]
        ],
        "devices_by_highest": data.get("devices_by_highest"),
    }


@dataclass(frozen=True, kw_only=True)
class DeviceSecuritySensorEntityDescription(SensorEntityDescription):
    """Describes a Device Security sensor."""

    value_fn: Callable[[dict[str, Any]], Any]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSORS: tuple[DeviceSecuritySensorEntityDescription, ...] = (
    DeviceSecuritySensorEntityDescription(
        key="devices_critical",
        translation_key="devices_critical",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _band(data, "devices_by_highest", "critical"),
    ),
    DeviceSecuritySensorEntityDescription(
        key="devices_high",
        translation_key="devices_high",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _band(data, "devices_by_highest", "high"),
    ),
    DeviceSecuritySensorEntityDescription(
        key="devices_at_risk",
        translation_key="devices_at_risk",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("devices_at_risk"),
        attributes_fn=_devices_at_risk,
    ),
    DeviceSecuritySensorEntityDescription(
        key="vulnerabilities_critical",
        translation_key="vulnerabilities_critical",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _band(data, "vulnerabilities", "critical"),
    ),
    DeviceSecuritySensorEntityDescription(
        key="vulnerabilities_high",
        translation_key="vulnerabilities_high",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _band(data, "vulnerabilities", "high"),
    ),
    DeviceSecuritySensorEntityDescription(
        key="vulnerabilities_total",
        translation_key="vulnerabilities_total",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _band(data, "vulnerabilities", "total"),
    ),
    DeviceSecuritySensorEntityDescription(
        key="linked_devices",
        translation_key="linked_devices",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (data.get("home_assistant") or {}).get("linked_devices"),
    ),
    DeviceSecuritySensorEntityDescription(
        key="last_sync",
        translation_key="last_sync",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last_sync,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DeviceSecurityConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Device Security sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        DeviceSecuritySensor(coordinator, entry, description) for description in SENSORS
    )


class DeviceSecuritySensor(CoordinatorEntity[DeviceSecurityCoordinator], SensorEntity):
    """A value from the platform summary."""

    _attr_has_entity_name = True
    entity_description: DeviceSecuritySensorEntityDescription

    def __init__(
        self,
        coordinator: DeviceSecurityCoordinator,
        entry: DeviceSecurityConfigEntry,
        description: DeviceSecuritySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Device Security",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=entry.data.get(CONF_URL),
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data or {})
