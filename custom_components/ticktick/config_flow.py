"""Config flow for TickTick Integration."""

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=60,
                    step=1,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Coerce(int),
        )
    }
)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle TickTick Integration OAuth2 authentication."""

    DOMAIN = DOMAIN

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "TickTickOptionsFlow":
        """Return the options flow."""
        return TickTickOptionsFlow()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start a new sign-in when the access token has expired."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to sign in to TickTick again."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create the entry, or update the existing one after a re-auth."""
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        return await super().async_oauth_create_entry(data)


class TickTickOptionsFlow(OptionsFlowWithReload):
    """Options for TickTick; saving them reloads the entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set how often TickTick is polled."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
