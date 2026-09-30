"""Fixtures for Device Security tests."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import CONF_API_TOKEN, CONF_URL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.device_security.const import CONF_TENANT, DOMAIN

URL = "https://api.example.test"

SUMMARY: dict[str, Any] = {
    "status": True,
    "message": "Success",
    "data": {
        "devices_total": 24,
        "devices_at_risk": 3,
        "devices_by_highest": {"critical": 1, "high": 1, "medium": 1, "low": 0},
        "vulnerabilities": {
            "critical": 2,
            "high": 4,
            "medium": 5,
            "low": 1,
            "total": 12,
        },
        "home_assistant": {
            "linked_devices": 18,
            "last_sync_at": "2026-09-25T15:00:00+00:00",
            "devices_at_risk": [
                {
                    "ha_device_id": "abc",
                    "device_id": 812,
                    "name": "Hall light",
                    "vulnerabilities": 2,
                    "highest": "critical",
                }
            ],
        },
    },
}


@pytest.fixture(autouse=True, scope="session")
def pycares_shutdown_thread():
    """Start pycares' process-wide shutdown thread before any test.

    pycares 5 starts it on the first resolver channel it closes and keeps it
    for the life of the process; the per-test lingering thread check would
    otherwise fail whichever test first opens an aiohttp session.
    """
    try:
        import pycares
    except ImportError:
        return
    channel = pycares.Channel()
    if hasattr(channel, "close"):
        channel.close()
    del channel


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components in every test."""
    yield


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Device Security (demo)",
        unique_id=f"{URL}|demo",
        data={CONF_URL: URL, CONF_TENANT: "demo", CONF_API_TOKEN: "1|token"},
    )
