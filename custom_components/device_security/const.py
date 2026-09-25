"""Constants for the Device Security integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "device_security"

CONF_TENANT: Final = "tenant"

REGISTRY_PATH: Final = "/api/v1/home-assistant/registry"
SUMMARY_PATH: Final = "/api/v1/home-assistant/summary"

# How often the summary sensors refresh.
SUMMARY_INTERVAL: Final = timedelta(minutes=30)
# How often the device registry is posted, on top of start-up and registry changes.
REGISTRY_INTERVAL: Final = timedelta(hours=6)
# Registry changes arrive in bursts (a new Zigbee device adds several entities).
REGISTRY_DEBOUNCE_SECONDS: Final = 60

# Server-side limits (App\Integrations\HomeAssistant\Support\HomeAssistantRegistry).
MAX_DEVICES: Final = 2000
MAX_STRING: Final = 255
MAX_CONNECTIONS: Final = 16
MAX_DOMAINS: Final = 64

REQUEST_TIMEOUT: Final = 30
