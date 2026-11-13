"""Tests for setting up, unloading and re-authenticating the config entry."""

import time

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ticktick.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN

from .conftest import (
    ENTITY_ID,
    PROJECT_DATA_URL,
    PROJECTS_URL,
    TASK,
    project_data,
    reset_api,
)


def _reauth_flows(hass: HomeAssistant) -> list:
    return [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN and flow["context"]["source"] == SOURCE_REAUTH
    ]


async def test_setup_and_unload(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The entry loads, creates one to-do list per project and unloads."""
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == "1"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_expired_token_starts_reauth(
    hass: HomeAssistant,
    credentials: None,
    mock_api: AiohttpClientMocker,
) -> None:
    """An expired token without refresh token asks the user to sign in again."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "old",
                "token_type": "bearer",
                "expires_in": 3600,
                "expires_at": time.time() - 100,
            },
        },
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert len(_reauth_flows(hass)) == 1


async def test_rejected_token_starts_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    credentials: None,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A 401 from TickTick asks the user to sign in again."""
    aioclient_mock.get(PROJECTS_URL, status=401)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert len(_reauth_flows(hass)) == 1


async def test_rejected_token_while_running_starts_reauth(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A 401 during a later poll asks the user to sign in again."""
    reset_api(aioclient_mock)
    aioclient_mock.get(PROJECT_DATA_URL, status=401)

    await setup_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert len(_reauth_flows(hass)) == 1


async def test_reauth_flow_updates_entry(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth,
    current_request_with_host: None,
) -> None:
    """Signing in again replaces the token on the existing entry."""
    entry = setup_integration

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"].startswith(OAUTH2_AUTHORIZE)

    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={"access_token": "new", "token_type": "bearer", "expires_in": 3600},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"]["access_token"] == "new"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED


async def test_poll_picks_up_changes(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A refresh shows tasks added in TickTick."""
    reset_api(aioclient_mock)
    aioclient_mock.get(
        PROJECT_DATA_URL,
        json=project_data(TASK, {**TASK, "id": "task2", "title": "Bread"}),
    )

    await setup_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == "2"
