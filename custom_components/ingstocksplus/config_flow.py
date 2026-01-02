from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_ISIN,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_ISIN): str,
                    vol.Optional(CONF_NAME): str,
                    vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                        int, vol.Range(min=1, max=360)
                    ),
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        isin = user_input[CONF_ISIN].strip().upper()
        name = (user_input.get(CONF_NAME) or "").strip()
        scan_interval = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        await self.async_set_unique_id(f"{DOMAIN}_{isin}")
        self._abort_if_unique_id_configured()

        title = name if name else f"ING {isin}"

        return self.async_create_entry(
            title=title,
            data={
                CONF_ISIN: isin,
                CONF_NAME: name,
                CONF_SCAN_INTERVAL: scan_interval,
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for changing scan interval/name after setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        entry = self._config_entry

        current_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        current_interval = int(current_interval)

        current_name = entry.options.get(CONF_NAME)
        if current_name is None:
            current_name = entry.data.get(CONF_NAME)
        if current_name is None:
            current_name = ""
        current_name = str(current_name)

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=current_name): str,
                vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    int, vol.Range(min=1, max=360)
                ),
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=schema)

        name = (user_input.get(CONF_NAME) or "").strip()
        scan_interval = int(user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        return self.async_create_entry(
            title="",
            data={
                CONF_NAME: name,
                CONF_SCAN_INTERVAL: scan_interval,
            },
        )