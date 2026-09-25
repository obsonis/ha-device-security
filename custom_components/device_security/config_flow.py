"""Config flow for Device Security: API URL, tenant and API token."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import DeviceSecurityApiClient, DeviceSecurityAuthError, DeviceSecurityConnectionError
from .const import CONF_TENANT, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_TENANT): str,
        vol.Required(CONF_API_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class DeviceSecurityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Device Security."""

    VERSION = 1

    async def _async_validate(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Call the summary endpoint with the credentials; return form errors."""
        client = DeviceSecurityApiClient(
            async_get_clientsession(self.hass),
            data[CONF_URL],
            data[CONF_API_TOKEN],
            data.get(CONF_TENANT),
        )
        try:
            await client.async_get_summary()
        except DeviceSecurityAuthError:
            return {"base": "invalid_auth"}
        except DeviceSecurityConnectionError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error validating platform credentials")
            return {"base": "unknown"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for URL, tenant and token."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = {
                **user_input,
                CONF_URL: user_input[CONF_URL].strip().rstrip("/"),
                CONF_TENANT: user_input[CONF_TENANT].strip().lower(),
                CONF_API_TOKEN: user_input[CONF_API_TOKEN].strip(),
            }
            await self.async_set_unique_id(
                f"{user_input[CONF_URL]}|{user_input[CONF_TENANT]}".lower()
            )
            self._abort_if_unique_id_configured()

            errors = await self._async_validate(user_input)
            if not errors:
                return self.async_create_entry(
                    title=f"Device Security ({user_input[CONF_TENANT]})", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """The token was refused; ask for a new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new token."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            data = {**entry.data, CONF_API_TOKEN: user_input[CONF_API_TOKEN].strip()}
            errors = await self._async_validate(data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors
        )
