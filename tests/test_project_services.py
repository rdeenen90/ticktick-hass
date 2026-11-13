"""Tests for the TickTick project services."""

import json

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ticktick.const import (
    DOMAIN,
    GET_PROJECT,
    GET_PROJECTS_WITH_TASKS,
)

from .conftest import (
    ENTITY_ID,
    PROJECT,
    PROJECT_DATA_URL,
    PROJECT_ID,
    PROJECTS_URL,
    TASK,
    project_data,
    reset_api,
)

PROJECT_URL = f"https://{GET_PROJECT.format(projectId=PROJECT_ID)}"

NEW_PROJECT = {**PROJECT, "id": "project2", "name": "Chores"}
NEW_PROJECT_DATA_URL = (
    f"https://{GET_PROJECTS_WITH_TASKS.format(projectId='project2')}"
)


async def _call(hass: HomeAssistant, service: str, data: dict) -> dict:
    response = await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    return response


def _posted(aioclient_mock: AiohttpClientMocker, url: str) -> dict:
    """Return the JSON body of the last POST to url."""
    bodies = [
        call[2]
        for call in aioclient_mock.mock_calls
        if call[0] == "POST" and str(call[1]) == url
    ]
    assert bodies, f"no POST to {url}"
    return json.loads(bodies[-1])


async def test_get_project(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """get_project returns the raw project."""
    aioclient_mock.get(PROJECT_URL, json=PROJECT)

    response = await _call(hass, "get_project", {"projectId": PROJECT_ID})

    assert response == {"data": PROJECT}


async def test_get_detailed_project(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """get_detailed_project returns the project with its tasks."""
    response = await _call(hass, "get_detailed_project", {"projectId": PROJECT_ID})

    assert response == {"data": project_data(TASK)}


async def test_create_project_adds_a_list(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """create_project sends only the given fields and the new list appears."""
    reset_api(aioclient_mock, projects=[PROJECT, NEW_PROJECT])
    aioclient_mock.post(PROJECTS_URL, json=NEW_PROJECT)
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data(TASK))
    aioclient_mock.get(
        NEW_PROJECT_DATA_URL,
        json={"project": NEW_PROJECT, "tasks": [], "columns": []},
    )

    response = await _call(
        hass, "create_project", {"name": "Chores", "color": "#F18181"}
    )

    assert response == {"data": NEW_PROJECT}
    assert _posted(aioclient_mock, PROJECTS_URL) == {
        "name": "Chores",
        "color": "#F18181",
    }
    assert hass.states.get("todo.chores").state == "0"
    assert hass.states.get(ENTITY_ID).state == "1"


async def test_update_project_renames_the_list(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """update_project sends only the given fields and the list is renamed."""
    renamed = {**PROJECT, "name": "Food"}
    reset_api(aioclient_mock, projects=[renamed])
    aioclient_mock.post(PROJECT_URL, json=renamed)
    aioclient_mock.get(
        PROJECT_DATA_URL, json={"project": renamed, "tasks": [TASK], "columns": []}
    )

    response = await _call(
        hass, "update_project", {"projectId": PROJECT_ID, "name": "Food"}
    )

    assert response == {"data": renamed}
    assert _posted(aioclient_mock, PROJECT_URL) == {"name": "Food"}
    # The entity keeps its id; only the name changes
    assert hass.states.get(ENTITY_ID).name == "Food"


async def test_delete_project_removes_the_list(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """delete_project deletes the project and its to-do list entity."""
    reset_api(aioclient_mock, projects=[])
    aioclient_mock.delete(PROJECT_URL, text="")

    response = await _call(hass, "delete_project", {"projectId": PROJECT_ID})

    assert response == {"data": {"status": "Success"}}
    assert hass.states.get(ENTITY_ID) is None
    assert entity_registry.async_get(ENTITY_ID) is None


async def test_project_id_is_required(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Project services reject a call without a project id."""
    with pytest.raises(vol.Invalid):
        await _call(hass, "delete_project", {})


async def test_unknown_view_mode_is_rejected(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """create_project rejects a view mode TickTick does not know."""
    with pytest.raises(vol.Invalid):
        await _call(hass, "create_project", {"name": "Chores", "viewMode": "grid"})


async def test_project_api_error_is_raised(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A failing TickTick call fails the service call and keeps the list."""
    aioclient_mock.delete(PROJECT_URL, status=500, json={"errorMessage": "boom"})

    with pytest.raises(HomeAssistantError, match="500"):
        await _call(hass, "delete_project", {"projectId": PROJECT_ID})

    assert hass.states.get(ENTITY_ID) is not None
