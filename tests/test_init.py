"""Setup, sensors and the registry post."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.device_security.const import REGISTRY_PATH, SUMMARY_PATH
from custom_components.device_security.registry import build_devices

from .conftest import SUMMARY, URL


def _add_zigbee_setup(hass: HomeAssistant) -> tuple[str, str, str]:
    """A Wi-Fi plug, a Zigbee coordinator and a bulb behind it, plus a service."""
    other = MockConfigEntry(domain="zha")
    other.add_to_hass(hass)
    device_registry = dr.async_get(hass)

    plug = device_registry.async_get_or_create(
        config_entry_id=other.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:02")},
        manufacturer="Shelly",
        model="Shelly Plus Plug S",
        sw_version="1.4.4",
        name="Plug",
    )
    coordinator = device_registry.async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={("zha", "coordinator")},
        connections={(dr.CONNECTION_ZIGBEE, "00:12:4b:00:24:c1:12:34")},
        manufacturer="ITead",
        model="Sonoff Zigbee 3.0 USB Dongle Plus",
    )
    bulb = device_registry.async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={("zha", "bulb")},
        connections={(dr.CONNECTION_ZIGBEE, "00:17:88:01:02:03:04:05")},
        manufacturer="Signify Netherlands B.V.",
        model="Hue white lamp",
        sw_version="1.104.2",
        via_device=("zha", "coordinator"),
    )
    er.async_get(hass).async_get_or_create(
        "light", "zha", "bulb-light", config_entry=other, device_id=bulb.id
    )
    return plug.id, coordinator.id, bulb.id


async def test_setup_creates_sensors(
    hass: HomeAssistant, aioclient_mock, config_entry: MockConfigEntry
) -> None:
    aioclient_mock.get(URL + SUMMARY_PATH, json=SUMMARY)
    aioclient_mock.post(URL + REGISTRY_PATH, status=202, json={"status": True})
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", "device_security", f"{config_entry.entry_id}_devices_critical"
    )
    assert hass.states.get(entity_id).state == "1"

    at_risk_id = entity_registry.async_get_entity_id(
        "sensor", "device_security", f"{config_entry.entry_id}_devices_at_risk"
    )
    at_risk = hass.states.get(at_risk_id)
    assert at_risk.state == "3"
    assert at_risk.attributes["devices"][0]["name"] == "Hall light"

    total_id = entity_registry.async_get_entity_id(
        "sensor", "device_security", f"{config_entry.entry_id}_vulnerabilities_total"
    )
    assert hass.states.get(total_id).state == "12"


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant, aioclient_mock, config_entry: MockConfigEntry
) -> None:
    aioclient_mock.get(URL + SUMMARY_PATH, status=401)
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_registry_post_carries_devices(
    hass: HomeAssistant, aioclient_mock, config_entry: MockConfigEntry
) -> None:
    plug_id, coordinator_id, bulb_id = _add_zigbee_setup(hass)
    aioclient_mock.get(URL + SUMMARY_PATH, json=SUMMARY)
    aioclient_mock.post(URL + REGISTRY_PATH, status=202, json={"status": True})
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await config_entry.runtime_data.coordinator.async_sync_registry()

    posts = [call for call in aioclient_mock.mock_calls if call[0] == "POST"]
    assert posts
    payload = posts[-1][2]
    assert payload["instance_id"]
    devices = {device["id"]: device for device in payload["devices"]}

    assert devices[plug_id]["connections"] == [["mac", "aa:bb:cc:dd:ee:02"]]
    assert devices[plug_id]["integration"] == "zha"
    assert devices[bulb_id]["via_device_id"] == coordinator_id
    assert devices[bulb_id]["sw_version"] == "1.104.2"
    assert devices[bulb_id]["entity_domains"] == ["light"]
    # The integration's own service device is sent too; the server skips entry_type service.
    assert any(device["entry_type"] == "service" for device in devices.values())

    coordinator = config_entry.runtime_data.coordinator
    assert coordinator.last_registry_error is None
    assert coordinator.last_registry_devices == len(payload["devices"])


async def test_build_devices_caps_strings(hass: HomeAssistant) -> None:
    other = MockConfigEntry(domain="demo")
    other.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={("demo", "long")},
        manufacturer="x" * 400,
        model="  ",
    )

    device = build_devices(hass)[0]

    assert len(device["manufacturer"]) == 255
    assert device["model"] is None
