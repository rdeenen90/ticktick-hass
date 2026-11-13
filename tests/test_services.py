"""Tests for the TickTick services."""

import json

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ticktick.const import (
    COMPLETE_TASK,
    CREATE_TASK,
    DOMAIN,
    GET_TASK,
    UPDATE_TASK,
)

from .conftest import PROJECT, PROJECT_ID, TASK, TASK_ID

IDS = {"projectId": PROJECT_ID, "taskId": TASK_ID}
TASK_URL = f"https://{GET_TASK.format(**IDS)}"
CREATE_URL = f"https://{CREATE_TASK}"
UPDATE_URL = f"https://{UPDATE_TASK.format(taskId=TASK_ID)}"
COMPLETE_URL = f"https://{COMPLETE_TASK.format(**IDS)}"


async def _call(hass: HomeAssistant, service: str, data: dict | None = None) -> dict:
    return await hass.services.async_call(
        DOMAIN, service, data or {}, blocking=True, return_response=True
    )


def _calls(aioclient_mock: AiohttpClientMocker, method: str, url: str) -> list:
    return [
        call
        for call in aioclient_mock.mock_calls
        if call[0] == method and str(call[1]) == url
    ]


async def test_get_projects(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """get_projects returns the raw project list."""
    assert await _call(hass, "get_projects") == {"data": [PROJECT]}


async def test_get_task(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """get_task returns the raw task."""
    aioclient_mock.get(TASK_URL, json=TASK)

    assert await _call(hass, "get_task", IDS) == {"data": TASK}


async def test_create_task(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """create_task posts the task with the date in TickTick's format."""
    aioclient_mock.post(CREATE_URL, json={**TASK, "id": "task2"})

    response = await _call(
        hass,
        "create_task",
        {
            "projectId": PROJECT_ID,
            "title": "Bread",
            "dueDate": "2026-11-20 10:00:00",
            "timeZone": "Europe/Amsterdam",
            "priority": "HIGH",
        },
    )

    assert response["data"]["id"] == "task2"
    body = json.loads(_calls(aioclient_mock, "POST", CREATE_URL)[-1][2])
    assert body["title"] == "Bread"
    assert body["dueDate"] == "2026-11-20T10:00:00+0100"
    assert body["priority"] == 5


async def test_update_task_changes_only_given_fields(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """update_task fetches the task and changes only the given fields."""
    aioclient_mock.get(TASK_URL, json=TASK)
    aioclient_mock.post(UPDATE_URL, json={**TASK, "title": "Oat milk"})

    response = await _call(hass, "update_task", {**IDS, "title": "Oat milk"})

    assert response["data"]["title"] == "Oat milk"
    body = json.loads(_calls(aioclient_mock, "POST", UPDATE_URL)[-1][2])
    assert body["title"] == "Oat milk"
    assert body["content"] == "Two litres"


@pytest.mark.parametrize(
    ("service", "method", "url"),
    [
        ("complete_task", "POST", COMPLETE_URL),
        ("delete_task", "DELETE", TASK_URL),
    ],
)
async def test_complete_and_delete_task(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    service: str,
    method: str,
    url: str,
) -> None:
    """complete_task and delete_task call TickTick and refresh the lists."""
    aioclient_mock.request(method.lower(), url, text="")
    polls_before = aioclient_mock.call_count

    assert await _call(hass, service, IDS) == {"data": {"status": "Success"}}

    assert len(_calls(aioclient_mock, method, url)) == 1
    # The service call itself plus a refresh of only that list
    assert aioclient_mock.call_count == polls_before + 2


async def test_api_error_is_raised(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A failing TickTick call fails the service call."""
    aioclient_mock.post(COMPLETE_URL, status=500, json={"errorMessage": "boom"})

    with pytest.raises(HomeAssistantError, match="500"):
        await _call(hass, "complete_task", IDS)


async def test_update_task_requires_ids(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """update_task without ids is a validation error."""
    with pytest.raises(ServiceValidationError):
        await _call(hass, "update_task", {"title": "Oat milk"})


async def test_service_without_loaded_entry(hass: HomeAssistant) -> None:
    """Services exist without a config entry but refuse to run."""
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError):
        await _call(hass, "get_projects")
