"""Tests for picking lists and tasks by name and for emptying fields."""

import json

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ticktick.const import (
    COMPLETE_TASK,
    CREATE_TASK,
    DOMAIN,
    GET_TASK,
    UPDATE_TASK,
)

from .conftest import (
    ENTITY_ID,
    INBOX_ENTITY_ID,
    PROJECT_DATA_URL,
    PROJECT_ID,
    TASK,
    TASK_ID,
    project_data,
    reset_api,
)

IDS = {"projectId": PROJECT_ID, "taskId": TASK_ID}
TASK_URL = f"https://{GET_TASK.format(**IDS)}"
CREATE_URL = f"https://{CREATE_TASK}"
UPDATE_URL = f"https://{UPDATE_TASK.format(taskId=TASK_ID)}"
COMPLETE_URL = f"https://{COMPLETE_TASK.format(**IDS)}"

DUE = "2026-11-20T17:00:00.000+0000"
FULL_TASK = {
    **TASK,
    "startDate": DUE,
    "dueDate": DUE,
    "reminders": ["TRIGGER:PT0S"],
    "repeatFlag": "RRULE:FREQ=WEEKLY;INTERVAL=1",
    "items": [{"id": "i1", "title": "Skimmed", "status": 0}],
}


async def _call(hass: HomeAssistant, service: str, data: dict) -> dict:
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True
    )


def _posted(aioclient_mock: AiohttpClientMocker, url: str) -> dict:
    """Return the JSON body of the last POST to url."""
    bodies = [
        call[2]
        for call in aioclient_mock.mock_calls
        if call[0] == "POST" and str(call[1]) == url
    ]
    assert bodies, f"no POST to {url}"
    return json.loads(bodies[-1])


def _was_called(aioclient_mock: AiohttpClientMocker, method: str, url: str) -> bool:
    return any(
        call[0] == method and str(call[1]) == url for call in aioclient_mock.mock_calls
    )


# === Picking a list ===


async def test_create_task_in_a_list_entity(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A to-do list entity can be given in place of a project id."""
    aioclient_mock.post(CREATE_URL, json={**TASK, "id": "task2"})

    await _call(hass, "create_task", {"list": ENTITY_ID, "title": "Bread"})

    assert _posted(aioclient_mock, CREATE_URL)["projectId"] == PROJECT_ID


async def test_create_task_in_the_inbox(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The inbox list resolves to TickTick's inbox id."""
    aioclient_mock.post(CREATE_URL, json={**TASK, "id": "task2", "projectId": "inbox1"})

    await _call(hass, "create_task", {"list": INBOX_ENTITY_ID, "title": "Bread"})

    assert _posted(aioclient_mock, CREATE_URL)["projectId"] == "inbox"


async def test_project_service_with_a_list_entity(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Project services take a to-do list entity too."""
    response = await _call(hass, "get_detailed_project", {"list": ENTITY_ID})

    assert response == {"data": project_data(TASK)}


@pytest.mark.parametrize("data", [{}, {"list": "todo.shopping_list"}])
async def test_list_must_be_a_ticktick_list(
    hass: HomeAssistant, setup_integration: MockConfigEntry, data: dict
) -> None:
    """A missing list, or one from another integration, is a validation error."""
    with pytest.raises(ServiceValidationError):
        await _call(hass, "create_task", {**data, "title": "Bread"})


# === Picking a task by title ===


async def test_complete_task_by_title(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A task can be picked by its title, ignoring case."""
    aioclient_mock.post(COMPLETE_URL, text="")

    await _call(hass, "complete_task", {"list": ENTITY_ID, "taskTitle": " milk "})

    assert _was_called(aioclient_mock, "POST", COMPLETE_URL)


async def test_update_task_by_title(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """update_task finds the task by taskTitle and can give it a new title."""
    aioclient_mock.get(TASK_URL, json=TASK)
    aioclient_mock.post(UPDATE_URL, json={**TASK, "title": "Oat milk"})

    await _call(
        hass,
        "update_task",
        {"list": ENTITY_ID, "taskTitle": "Milk", "title": "Oat milk"},
    )

    assert _posted(aioclient_mock, UPDATE_URL)["title"] == "Oat milk"


@pytest.mark.parametrize(
    ("tasks", "message"),
    [
        ([TASK], "No open task titled 'Bread'"),
        ([{**TASK, "title": "Bread"}, {**TASK, "id": "t2", "title": "bread"}], "2 open"),
        # A completed task with that title does not count
        ([{**TASK, "title": "Bread", "status": 2}], "No open task titled 'Bread'"),
    ],
)
async def test_task_title_must_match_exactly_one_open_task(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    tasks: list[dict],
    message: str,
) -> None:
    """No match or several matches fail without changing anything."""
    reset_api(aioclient_mock)
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data(*tasks))

    with pytest.raises(ServiceValidationError, match=message):
        await _call(hass, "complete_task", {"list": ENTITY_ID, "taskTitle": "Bread"})

    assert not [call for call in aioclient_mock.mock_calls if call[0] == "POST"]


async def test_task_needs_an_id_or_a_title(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """A task service without taskId or taskTitle is a validation error."""
    with pytest.raises(ServiceValidationError, match="taskId or a taskTitle"):
        await _call(hass, "complete_task", {"list": ENTITY_ID})


# === Emptying fields ===


async def test_update_task_empties_fields(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Empty values are sent the way TickTick needs them to empty a field."""
    aioclient_mock.get(TASK_URL, json=FULL_TASK)
    aioclient_mock.post(UPDATE_URL, json=TASK)

    await _call(
        hass,
        "update_task",
        {
            **IDS,
            "dueDate": None,
            "reminders": [],
            "items": [],
            "repeatFlag": "",
            "content": "",
        },
    )

    body = _posted(aioclient_mock, UPDATE_URL)
    assert body["dueDate"] is None
    assert body["startDate"] is None
    assert body["reminders"] == []
    assert body["items"] == []
    assert body["repeatFlag"] == ""
    assert body["content"] == ""


async def test_update_task_keeps_fields_it_is_not_given(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Changing one field leaves the others as they were."""
    aioclient_mock.get(TASK_URL, json=FULL_TASK)
    aioclient_mock.post(UPDATE_URL, json=FULL_TASK)

    await _call(hass, "update_task", {**IDS, "title": "Oat milk"})

    body = _posted(aioclient_mock, UPDATE_URL)
    assert body["dueDate"] == DUE
    assert body["reminders"] == ["TRIGGER:PT0S"]
    assert body["repeatFlag"] == "RRULE:FREQ=WEEKLY;INTERVAL=1"
    assert [item["title"] for item in body["items"]] == ["Skimmed"]


async def _setup_due_task(
    hass: HomeAssistant, entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    reset_api(aioclient_mock)
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data(FULL_TASK))
    aioclient_mock.post(UPDATE_URL, json=FULL_TASK)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_todo_item_due_date_can_be_removed(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Removing the due date in Home Assistant removes it in TickTick."""
    await _setup_due_task(hass, setup_integration, aioclient_mock)

    await hass.services.async_call(
        "todo",
        "update_item",
        {"item": TASK_ID, "due_datetime": None},
        target={"entity_id": ENTITY_ID},
        blocking=True,
    )

    body = _posted(aioclient_mock, UPDATE_URL)
    assert body["dueDate"] is None
    assert body["startDate"] is None


async def test_todo_item_description_can_be_removed(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Removing the description in Home Assistant empties it in TickTick."""
    await _setup_due_task(hass, setup_integration, aioclient_mock)

    await hass.services.async_call(
        "todo",
        "update_item",
        {"item": TASK_ID, "description": None},
        target={"entity_id": ENTITY_ID},
        blocking=True,
    )

    body = _posted(aioclient_mock, UPDATE_URL)
    assert body["content"] == ""
    assert body["dueDate"] == DUE


async def test_todo_item_rename_keeps_the_due_date(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Renaming an item does not touch its due date."""
    await _setup_due_task(hass, setup_integration, aioclient_mock)

    await hass.services.async_call(
        "todo",
        "update_item",
        {"item": TASK_ID, "rename": "Oat milk"},
        target={"entity_id": ENTITY_ID},
        blocking=True,
    )

    body = _posted(aioclient_mock, UPDATE_URL)
    assert body["title"] == "Oat milk"
    assert body["dueDate"] == DUE
    assert body["startDate"] == DUE
