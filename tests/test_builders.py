"""Tests for the reminder, repeat and subtask builders."""

import json

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ticktick.builders import (
    build_items,
    build_reminder,
    build_reminders,
    build_repeat_flag,
)
from custom_components.ticktick.const import CREATE_TASK, DOMAIN, GET_TASK, UPDATE_TASK

from .conftest import PROJECT_ID, TASK, TASK_ID

IDS = {"projectId": PROJECT_ID, "taskId": TASK_ID}
TASK_URL = f"https://{GET_TASK.format(**IDS)}"
CREATE_URL = f"https://{CREATE_TASK}"
UPDATE_URL = f"https://{UPDATE_TASK.format(taskId=TASK_ID)}"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("TRIGGER:P0DT9H0M0S", "TRIGGER:P0DT9H0M0S"),
        ("on time", "TRIGGER:PT0S"),
        ("0", "TRIGGER:PT0S"),
        (0, "TRIGGER:PT0S"),
        (15, "TRIGGER:-PT15M"),
        ("15", "TRIGGER:-PT15M"),
        ("30 minutes", "TRIGGER:-PT30M"),
        ("30m", "TRIGGER:-PT30M"),
        ("2 hours before", "TRIGGER:-PT120M"),
        ("1 Day", "TRIGGER:-PT1440M"),
        ("1 week", "TRIGGER:-PT10080M"),
        ("09:00", "TRIGGER:P0DT9H0M0S"),
        ("18:30", "TRIGGER:P0DT18H30M0S"),
    ],
)
def test_build_reminder(value, expected) -> None:
    """Friendly reminders become TickTick triggers."""
    assert build_reminder(value) == expected


@pytest.mark.parametrize("value", ["soon", "3 fortnights", "25:00", True, 1.5, {}])
def test_build_reminder_rejects_unknown(value) -> None:
    """An unknown reminder is an error, not silently dropped."""
    with pytest.raises(ValueError):
        build_reminder(value)


def test_build_reminders_accepts_one_or_many() -> None:
    """A single reminder and a list both give a list."""
    assert build_reminders(None) == []
    assert build_reminders("1 hour") == ["TRIGGER:-PT60M"]
    assert build_reminders(["on time", "1 day"]) == [
        "TRIGGER:PT0S",
        "TRIGGER:-PT1440M",
    ]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("RRULE:FREQ=DAILY;INTERVAL=1", "RRULE:FREQ=DAILY;INTERVAL=1"),
        ("FREQ=WEEKLY;BYDAY=MO", "RRULE:FREQ=WEEKLY;BYDAY=MO"),
        ("daily", "RRULE:FREQ=DAILY;INTERVAL=1"),
        ("Weekly", "RRULE:FREQ=WEEKLY;INTERVAL=1"),
        ("monthly", "RRULE:FREQ=MONTHLY;INTERVAL=1"),
        ("yearly", "RRULE:FREQ=YEARLY;INTERVAL=1"),
        ("weekdays", "RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,TU,WE,TH,FR"),
        ("every 2 weeks", "RRULE:FREQ=WEEKLY;INTERVAL=2"),
        ("every month", "RRULE:FREQ=MONTHLY;INTERVAL=1"),
    ],
)
def test_build_repeat_flag(value, expected) -> None:
    """Friendly repeat rules become TickTick rules."""
    assert build_repeat_flag(value) == expected


@pytest.mark.parametrize("value", ["sometimes", "every 0 days", "every 2 moons", "", 7])
def test_build_repeat_flag_rejects_unknown(value) -> None:
    """An unknown repeat rule is an error."""
    with pytest.raises(ValueError):
        build_repeat_flag(value)


def test_build_items() -> None:
    """Subtasks come from titles or objects."""
    items = build_items(
        ["Milk", {"title": "Bread", "completed": True}, {"title": "Eggs", "id": "i1"}]
    )

    assert [item.title for item in items] == ["Milk", "Bread", "Eggs"]
    assert [int(item.status) for item in items] == [0, 1, 0]
    assert [item.id for item in items] == [None, None, "i1"]
    assert build_items(None) == []


@pytest.mark.parametrize("value", ["Milk", [{"completed": True}], [""], [3]])
def test_build_items_rejects_invalid(value) -> None:
    """Subtasks need to be a list of things with a title."""
    with pytest.raises(ValueError):
        build_items(value)


def _posted(aioclient_mock: AiohttpClientMocker, url: str) -> dict:
    bodies = [
        call[2]
        for call in aioclient_mock.mock_calls
        if call[0] == "POST" and str(call[1]) == url
    ]
    assert bodies, f"no POST to {url}"
    return json.loads(bodies[-1])


async def test_create_task_with_subtasks_reminders_and_repeat(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """create_task sends subtasks, reminders and the repeat rule to TickTick."""
    aioclient_mock.post(CREATE_URL, json={**TASK, "id": "task2"})

    await hass.services.async_call(
        DOMAIN,
        "create_task",
        {
            "projectId": PROJECT_ID,
            "title": "Shopping",
            "items": ["Milk", {"title": "Bread", "completed": True}],
            "reminders": ["on time", "1 hour"],
            "repeatFlag": "weekly",
        },
        blocking=True,
        return_response=True,
    )

    body = _posted(aioclient_mock, CREATE_URL)
    assert body["items"] == [
        {"title": "Milk", "status": 0},
        {"title": "Bread", "status": 1},
    ]
    assert body["reminders"] == ["TRIGGER:PT0S", "TRIGGER:-PT60M"]
    assert body["repeatFlag"] == "RRULE:FREQ=WEEKLY;INTERVAL=1"


async def test_create_task_without_extras_sends_none(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A plain create_task does not send empty subtasks, reminders or repeat."""
    aioclient_mock.post(CREATE_URL, json={**TASK, "id": "task2"})

    await hass.services.async_call(
        DOMAIN,
        "create_task",
        {"projectId": PROJECT_ID, "title": "Shopping"},
        blocking=True,
        return_response=True,
    )

    body = _posted(aioclient_mock, CREATE_URL)
    assert not {"items", "reminders", "repeatFlag"} & body.keys()


async def test_update_task_replaces_subtasks(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """update_task replaces the subtasks and keeps the ones passed with an id."""
    existing = {**TASK, "items": [{"id": "i1", "title": "Milk", "status": 0}]}
    aioclient_mock.get(TASK_URL, json=existing)
    aioclient_mock.post(UPDATE_URL, json=existing)

    await hass.services.async_call(
        DOMAIN,
        "update_task",
        {
            **IDS,
            "items": [{"id": "i1", "title": "Milk", "completed": True}, "Bread"],
            "reminders": "30 minutes",
            "repeatFlag": "every 2 days",
        },
        blocking=True,
        return_response=True,
    )

    body = _posted(aioclient_mock, UPDATE_URL)
    assert body["items"] == [
        {"id": "i1", "title": "Milk", "status": 1},
        {"title": "Bread", "status": 0},
    ]
    assert body["reminders"] == ["TRIGGER:-PT30M"]
    assert body["repeatFlag"] == "RRULE:FREQ=DAILY;INTERVAL=2"


@pytest.mark.parametrize(
    "extra",
    [{"reminders": "soon"}, {"repeatFlag": "sometimes"}, {"items": "Milk"}],
)
async def test_invalid_input_is_a_validation_error(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    extra: dict,
) -> None:
    """Bad reminders, repeat rules or subtasks fail before TickTick is called."""
    aioclient_mock.get(TASK_URL, json=TASK)
    for service, data in (
        ("create_task", {"projectId": PROJECT_ID, "title": "Shopping"}),
        ("update_task", IDS),
    ):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                service,
                {**data, **extra},
                blocking=True,
                return_response=True,
            )

    assert not [call for call in aioclient_mock.mock_calls if call[0] == "POST"]
