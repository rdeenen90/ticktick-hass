"""Tests for the TickTick to-do lists."""

import json
from datetime import UTC, datetime

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ticktick.const import COMPLETE_TASK, CREATE_TASK, UPDATE_TASK

from .conftest import (
    ENTITY_ID,
    PROJECT_DATA_URL,
    PROJECT_ID,
    TASK,
    TASK_ID,
    project_data,
)

CREATE_URL = f"https://{CREATE_TASK}"
UPDATE_URL = f"https://{UPDATE_TASK.format(taskId=TASK_ID)}"
COMPLETE_URL = (
    f"https://{COMPLETE_TASK.format(projectId=PROJECT_ID, taskId=TASK_ID)}"
)


async def _get_items(hass: HomeAssistant) -> list[dict]:
    response = await hass.services.async_call(
        "todo",
        "get_items",
        {},
        target={"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    return response[ENTITY_ID]["items"]


async def _refresh(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


def _posted(aioclient_mock: AiohttpClientMocker, url: str) -> dict:
    """Return the JSON body of the last POST to url."""
    bodies = [
        call[2]
        for call in aioclient_mock.mock_calls
        if call[0] == "POST" and str(call[1]) == url
    ]
    assert bodies, f"no POST to {url}"
    return json.loads(bodies[-1])


async def test_items(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    """Tasks show up as to-do items."""
    items = await _get_items(hass)

    assert len(items) == 1
    assert items[0]["uid"] == TASK_ID
    assert items[0]["summary"] == "Milk"
    assert items[0]["description"] == "Two litres"
    assert items[0]["status"] == "needs_action"


async def test_emptied_list_clears_items(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The last task disappears when the list becomes empty."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data())

    await _refresh(hass, setup_integration)

    assert hass.states.get(ENTITY_ID).state == "0"
    assert await _get_items(hass) == []


async def test_all_day_due_is_a_date(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """An all-day task is due on a date, in the task's own time zone."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        PROJECT_DATA_URL,
        json=project_data(
            {
                **TASK,
                "isAllDay": True,
                # Midnight on 27 October in Amsterdam
                "dueDate": "2026-10-26T23:00:00.000+0000",
                "timeZone": "Europe/Amsterdam",
            }
        ),
    )

    await _refresh(hass, setup_integration)

    assert (await _get_items(hass))[0]["due"] == "2026-10-27"


async def test_timed_due_is_a_datetime(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A task with a time is due at that moment."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        PROJECT_DATA_URL,
        json=project_data({**TASK, "dueDate": "2026-11-20T09:30:00.000+0000"}),
    )

    await _refresh(hass, setup_integration)

    due = dt_util.parse_datetime((await _get_items(hass))[0]["due"])
    assert due == datetime(2026, 11, 20, 9, 30, tzinfo=UTC)


async def test_checklist_uses_desc(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A checklist task shows its desc field as the description."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        PROJECT_DATA_URL,
        json=project_data({**TASK, "kind": "CHECKLIST", "desc": "From desc"}),
    )

    await _refresh(hass, setup_integration)

    assert (await _get_items(hass))[0]["description"] == "From desc"


async def test_add_item_with_due_date(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Adding an item with only a date creates an all-day task."""
    aioclient_mock.post(CREATE_URL, json={**TASK, "id": "task2", "title": "Bread"})

    await hass.services.async_call(
        "todo",
        "add_item",
        {"item": "Bread", "due_date": "2026-11-20"},
        target={"entity_id": ENTITY_ID},
        blocking=True,
    )

    body = _posted(aioclient_mock, CREATE_URL)
    assert body["title"] == "Bread"
    assert body["projectId"] == PROJECT_ID
    assert body["isAllDay"] is True
    assert body["dueDate"].startswith("2026-11-20T00:00:00")
    assert body["startDate"] == body["dueDate"]


async def test_add_item_with_due_datetime(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Adding an item with a date and time creates a timed task."""
    aioclient_mock.post(CREATE_URL, json={**TASK, "id": "task2", "title": "Bread"})

    await hass.services.async_call(
        "todo",
        "add_item",
        {"item": "Bread", "due_datetime": "2026-11-20T09:30:00+00:00"},
        target={"entity_id": ENTITY_ID},
        blocking=True,
    )

    body = _posted(aioclient_mock, CREATE_URL)
    assert body["isAllDay"] is False
    due = datetime.strptime(body["dueDate"], "%Y-%m-%dT%H:%M:%S%z")
    assert due == datetime(2026, 11, 20, 9, 30, tzinfo=UTC)


async def test_rename_item(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Renaming an item updates the task and keeps its other fields."""
    aioclient_mock.post(UPDATE_URL, json={**TASK, "title": "Oat milk"})

    await hass.services.async_call(
        "todo",
        "update_item",
        {"item": TASK_ID, "rename": "Oat milk"},
        target={"entity_id": ENTITY_ID},
        blocking=True,
    )

    body = _posted(aioclient_mock, UPDATE_URL)
    assert body["title"] == "Oat milk"
    assert body["content"] == "Two litres"
    assert body["id"] == TASK_ID


async def test_complete_item(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Checking an item off completes the task in TickTick."""
    aioclient_mock.post(COMPLETE_URL, text="")

    await hass.services.async_call(
        "todo",
        "update_item",
        {"item": TASK_ID, "status": "completed"},
        target={"entity_id": ENTITY_ID},
        blocking=True,
    )

    assert any(
        call[0] == "POST" and str(call[1]) == COMPLETE_URL
        for call in aioclient_mock.mock_calls
    )


async def test_remove_item(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Removing an item deletes the task in TickTick."""
    task_url = COMPLETE_URL.removesuffix("/complete")
    aioclient_mock.delete(task_url, text="")

    await hass.services.async_call(
        "todo",
        "remove_item",
        {"item": [TASK_ID]},
        target={"entity_id": ENTITY_ID},
        blocking=True,
    )

    assert any(
        call[0] == "DELETE" and str(call[1]) == task_url
        for call in aioclient_mock.mock_calls
    )
