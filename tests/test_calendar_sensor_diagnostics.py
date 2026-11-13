"""Tests for the calendars, the task count sensors and diagnostics."""

import json
from datetime import UTC, datetime

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ticktick.const import DOMAIN, GET_PROJECT
from custom_components.ticktick.diagnostics import async_get_config_entry_diagnostics

from .conftest import PROJECT_DATA_URL, PROJECT_ID, TASK, project_data, reset_api

CALENDAR_ID = "calendar.groceries"

# The tests run in US/Pacific: this is 04:00 on 20 November there
NOW = "2026-11-20T12:00:00+00:00"

TIMED = {**TASK, "id": "timed", "title": "Timed", "dueDate": "2026-11-20T20:00:00.000+0000"}
RANGE = {
    **TASK,
    "id": "range",
    "title": "Range",
    "startDate": "2026-11-21T09:00:00.000+0000",
    "dueDate": "2026-11-21T11:00:00.000+0000",
}
ALL_DAY = {
    **TASK,
    "id": "allday",
    "title": "All day",
    "isAllDay": True,
    "startDate": "2026-11-20T08:00:00.000+0000",
    "dueDate": "2026-11-20T08:00:00.000+0000",
    "timeZone": "America/Los_Angeles",
}
ALL_DAY_YESTERDAY = {
    **ALL_DAY,
    "id": "yesterday",
    "title": "Yesterday",
    "startDate": "2026-11-19T08:00:00.000+0000",
    "dueDate": "2026-11-19T08:00:00.000+0000",
}
PASSED_TODAY = {
    **TASK,
    "id": "passed",
    "title": "Passed today",
    "dueDate": "2026-11-20T09:00:00.000+0000",
}
LONG_AGO = {**TASK, "id": "old", "title": "Long ago", "dueDate": "2026-11-10T09:00:00.000+0000"}
UNDATED = {**TASK, "id": "undated", "title": "Undated"}

ALL_TASKS = (TIMED, RANGE, ALL_DAY, ALL_DAY_YESTERDAY, PASSED_TODAY, LONG_AGO, UNDATED)


async def _load_tasks(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    *tasks: dict,
) -> None:
    reset_api(aioclient_mock)
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data(*tasks))
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def _events(hass: HomeAssistant, start: str, end: str) -> dict[str, dict]:
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"start_date_time": start, "end_date_time": end},
        target={"entity_id": CALENDAR_ID},
        blocking=True,
        return_response=True,
    )
    return {event["summary"]: event for event in response[CALENDAR_ID]["events"]}


# === Calendar ===


async def test_calendar_events(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Tasks with a due date are calendar events; undated tasks are not."""
    freezer.move_to(NOW)
    await _load_tasks(hass, setup_integration, aioclient_mock, *ALL_TASKS)

    events = await _events(hass, "2026-11-20T00:00:00-08:00", "2026-11-22T00:00:00-08:00")

    assert set(events) == {"Timed", "Range", "All day", "Passed today"}
    # Only a due time: shown for half an hour from then
    assert dt_util.parse_datetime(events["Timed"]["start"]) == datetime(
        2026, 11, 20, 20, 0, tzinfo=UTC
    )
    assert dt_util.parse_datetime(events["Timed"]["end"]) == datetime(
        2026, 11, 20, 20, 30, tzinfo=UTC
    )
    # A start and a due time: shown from start to due
    assert dt_util.parse_datetime(events["Range"]["start"]) == datetime(
        2026, 11, 21, 9, 0, tzinfo=UTC
    )
    assert dt_util.parse_datetime(events["Range"]["end"]) == datetime(
        2026, 11, 21, 11, 0, tzinfo=UTC
    )
    # All-day: a date, ending the day after
    assert events["All day"]["start"] == "2026-11-20"
    assert events["All day"]["end"] == "2026-11-21"
    assert events["Timed"]["description"] == "Two litres"


async def test_calendar_state_is_the_next_event(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The calendar's state follows the current or next upcoming task."""
    freezer.move_to(NOW)
    await _load_tasks(hass, setup_integration, aioclient_mock, RANGE, LONG_AGO, UNDATED)

    state = hass.states.get(CALENDAR_ID)
    assert state.state == "off"
    assert state.attributes["message"] == "Range"

    await _load_tasks(hass, setup_integration, aioclient_mock, UNDATED)
    assert "message" not in hass.states.get(CALENDAR_ID).attributes


async def test_delete_project_removes_the_calendar(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Deleting a project removes its calendar along with its to-do list."""
    assert entity_registry.async_get(CALENDAR_ID) is not None
    reset_api(aioclient_mock, projects=[])
    aioclient_mock.delete(
        f"https://{GET_PROJECT.format(projectId=PROJECT_ID)}", text=""
    )

    await hass.services.async_call(
        DOMAIN, "delete_project", {"projectId": PROJECT_ID}, blocking=True
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(CALENDAR_ID) is None
    assert entity_registry.async_get("todo.groceries") is None


# === Sensors ===


async def test_task_count_sensors(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The sensors count open, overdue and due-today tasks across the lists."""
    freezer.move_to(NOW)
    await _load_tasks(hass, setup_integration, aioclient_mock, *ALL_TASKS)

    overdue = hass.states.get("sensor.ticktick_overdue_tasks")
    today = hass.states.get("sensor.ticktick_tasks_due_today")
    open_tasks = hass.states.get("sensor.ticktick_open_tasks")

    # A passed time today is overdue; an all-day task today is not
    assert overdue.state == "3"
    assert {task["title"] for task in overdue.attributes["tasks"]} == {
        "Yesterday",
        "Passed today",
        "Long ago",
    }
    # Due today includes the task whose time has already passed
    assert today.state == "3"
    assert {task["title"] for task in today.attributes["tasks"]} == {
        "Timed",
        "All day",
        "Passed today",
    }
    assert today.attributes["lists"] == {"Groceries": 3}
    assert today.attributes["tasks"][0]["list"] == "Groceries"

    assert open_tasks.state == "7"
    assert open_tasks.attributes["lists"] == {"Groceries": 7}
    assert "tasks" not in open_tasks.attributes


async def test_task_count_sensors_without_tasks(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """With nothing due the dated sensors are zero."""
    await _load_tasks(hass, setup_integration, aioclient_mock, UNDATED)

    assert hass.states.get("sensor.ticktick_overdue_tasks").state == "0"
    assert hass.states.get("sensor.ticktick_tasks_due_today").state == "0"
    assert hass.states.get("sensor.ticktick_open_tasks").state == "1"


# === Diagnostics ===


async def test_diagnostics_hold_no_personal_data(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Diagnostics give counts and settings, without token, titles or list names."""
    await _load_tasks(hass, setup_integration, aioclient_mock, *ALL_TASKS)

    diagnostics = await async_get_config_entry_diagnostics(hass, setup_integration)

    dumped = json.dumps(diagnostics)
    assert diagnostics["entry"]["data"]["token"] == "**REDACTED**"
    for secret in ("Groceries", "Timed", "Two litres", '"token": {'):
        assert secret not in dumped
    assert diagnostics["coordinator"] == {
        "last_update_success": True,
        "update_interval_seconds": 60.0,
    }
    groceries = next(item for item in diagnostics["lists"] if item["open_tasks"] == 7)
    assert groceries["tasks_with_due_date"] == 6
    assert groceries["all_day_tasks"] == 2
    assert groceries["failing"] is False
