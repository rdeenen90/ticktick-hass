"""The TickTick Integration integration."""

from __future__ import annotations

import datetime
import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.typing import ConfigType

from . import api
from .const import DOMAIN
from .coordinator import TickTickConfigEntry, TickTickCoordinator
from .service_handlers import async_register_services
from .ticktick_api_python.ticktick_api import TickTickAPIClient

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=1)

PLATFORMS = [Platform.TODO]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TickTick services."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TickTickConfigEntry) -> bool:
    """Set up TickTick Integration from a config entry."""

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # Using an aiohttp-based API lib
    aiohttp_session = aiohttp_client.async_get_clientsession(hass)
    auth = api.AsyncConfigEntryAuth(aiohttp_session, session)
    access_token = await auth.async_get_access_token()

    tickTickApiClient = TickTickAPIClient(access_token, aiohttp_session)

    coordinator = TickTickCoordinator(
        hass, _LOGGER, entry, SCAN_INTERVAL, tickTickApiClient, access_token
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TickTickConfigEntry) -> bool:
    """Unload a TickTick config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
