"""Config flow tests."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.device_security.const import CONF_TENANT, DOMAIN, SUMMARY_PATH

from .conftest import SUMMARY, URL

USER_INPUT = {CONF_URL: URL + "/", CONF_TENANT: " Demo ", CONF_API_TOKEN: "1|token"}


async def test_user_flow_creates_entry(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(URL + SUMMARY_PATH, json=SUMMARY)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.device_security.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_URL: URL,
        CONF_TENANT: "demo",
        CONF_API_TOKEN: "1|token",
    }

    _method, _url, _data, headers = aioclient_mock.mock_calls[0]
    assert headers["Authorization"] == "Bearer 1|token"
    assert headers["X-Tenant"] == "demo"


async def test_user_flow_invalid_auth(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(URL + SUMMARY_PATH, status=403)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(URL + SUMMARY_PATH, status=500)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_rejects_http_url(hass: HomeAssistant, aioclient_mock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, CONF_URL: "http://api.example.test"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_URL: "url_not_https"}
    assert aioclient_mock.call_count == 0
