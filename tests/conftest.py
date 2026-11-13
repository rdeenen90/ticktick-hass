"""Fixtures for the TickTick integration tests."""

import time

import pytest
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ticktick.const import (
    DOMAIN,
    GET_PROJECTS,
    GET_PROJECTS_WITH_TASKS,
)

PROJECT_ID = "project1"
TASK_ID = "task1"
ENTITY_ID = "todo.groceries"

PROJECTS_URL = f"https://{GET_PROJECTS}"
PROJECT_DATA_URL = f"https://{GET_PROJECTS_WITH_TASKS.format(projectId=PROJECT_ID)}"

PROJECT = {
    "id": PROJECT_ID,
    "name": "Groceries",
    "sortOrder": 0,
    "kind": "TASK",
    "viewMode": "list",
}

TASK = {
    "id": TASK_ID,
    "projectId": PROJECT_ID,
    "title": "Milk",
    "content": "Two litres",
    "status": 0,
    "priority": 0,
}


def project_data(*tasks: dict) -> dict:
    """Return a TickTick 'project with data' response."""
    return {"project": PROJECT, "tasks": list(tasks), "columns": []}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load the integration from custom_components."""
    return


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry with a valid access token and no refresh token."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "token",
                "token_type": "bearer",
                "expires_in": 3600,
                "expires_at": time.time() + 3600,
            },
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def credentials(hass: HomeAssistant) -> None:
    """Register the TickTick application credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential("client-id", "client-secret")
    )


@pytest.fixture
def mock_api(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock TickTick with one project holding one task."""
    aioclient_mock.get(PROJECTS_URL, json=[PROJECT])
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data(TASK))
    return aioclient_mock


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    credentials: None,
    mock_api: AiohttpClientMocker,
) -> MockConfigEntry:
    """Set up the integration against the mocked API."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
