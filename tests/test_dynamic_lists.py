"""Tests for lists following TickTick, failure isolation, the inbox and options."""

from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ticktick.const import GET_PROJECTS_WITH_TASKS

from .conftest import (
    ENTITY_ID,
    INBOX_DATA_URL,
    INBOX_ENTITY_ID,
    PROJECT,
    PROJECT_DATA_URL,
    TASK,
    project_data,
    reset_api,
)

CHORES = {**PROJECT, "id": "project2", "name": "Chores"}
CHORES_ENTITY_ID = "todo.chores"
CHORES_DATA_URL = f"https://{GET_PROJECTS_WITH_TASKS.format(projectId='project2')}"
CHORES_DATA = {"project": CHORES, "tasks": [], "columns": []}


async def _refresh(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_inbox_is_a_list(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The inbox shows up as a to-do list although TickTick does not list it."""
    assert hass.states.get(INBOX_ENTITY_ID).state == "0"

    reset_api(aioclient_mock, inbox=None)
    aioclient_mock.get(
        INBOX_DATA_URL,
        json={
            "tasks": [{**TASK, "id": "task9", "projectId": "inbox123"}],
            "columns": [],
        },
    )
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data(TASK))
    await _refresh(hass, setup_integration)

    assert hass.states.get(INBOX_ENTITY_ID).state == "1"
    assert hass.states.get(ENTITY_ID).state == "1"


async def test_lists_follow_ticktick(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """A list added, renamed or deleted in TickTick is followed without a reload."""
    assert hass.states.get(CHORES_ENTITY_ID) is None

    # Added in TickTick
    reset_api(aioclient_mock, projects=[PROJECT, CHORES])
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data(TASK))
    aioclient_mock.get(CHORES_DATA_URL, json=CHORES_DATA)
    await _refresh(hass, setup_integration)
    assert hass.states.get(CHORES_ENTITY_ID).state == "0"

    # Renamed in TickTick: the entity keeps its id and takes the new name
    renamed = {**CHORES, "name": "Housework"}
    reset_api(aioclient_mock, projects=[PROJECT, renamed])
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data(TASK))
    aioclient_mock.get(CHORES_DATA_URL, json={**CHORES_DATA, "project": renamed})
    await _refresh(hass, setup_integration)
    assert hass.states.get(CHORES_ENTITY_ID).name == "Housework"

    # Deleted in TickTick
    reset_api(aioclient_mock)
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data(TASK))
    await _refresh(hass, setup_integration)
    assert hass.states.get(CHORES_ENTITY_ID) is None
    assert entity_registry.async_get(CHORES_ENTITY_ID) is None
    assert hass.states.get(ENTITY_ID).state == "1"
    assert setup_integration.state is ConfigEntryState.LOADED


async def test_empty_project_list_keeps_the_lists(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """An empty project list is treated as a hiccup, not as every list deleted."""
    reset_api(aioclient_mock, projects=[])
    await _refresh(hass, setup_integration)

    assert entity_registry.async_get(ENTITY_ID) is not None


@pytest.mark.parametrize(
    "broken",
    [
        {"status": 500, "json": {"errorCode": "unknown_exception"}},
        # What TickTick answers for a project it no longer knows
        {"json": {}},
    ],
)
async def test_one_failing_list_does_not_break_the_others(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    broken: dict,
) -> None:
    """A list that fails keeps its last known tasks while the others update."""
    reset_api(aioclient_mock, projects=[PROJECT, CHORES])
    aioclient_mock.get(PROJECT_DATA_URL, **broken)
    aioclient_mock.get(CHORES_DATA_URL, json=CHORES_DATA)

    await _refresh(hass, setup_integration)
    await _refresh(hass, setup_integration)

    assert setup_integration.runtime_data.last_update_success
    assert hass.states.get(ENTITY_ID).state == "1"
    assert hass.states.get(CHORES_ENTITY_ID).state == "0"
    # Warned about once, not on every poll
    assert caplog.text.count("Could not update TickTick list Groceries") == 1


async def test_all_lists_failing_makes_them_unavailable(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """When nothing can be fetched the lists become unavailable."""
    reset_api(aioclient_mock, inbox=None)
    aioclient_mock.get(INBOX_DATA_URL, status=500, json={})
    aioclient_mock.get(PROJECT_DATA_URL, status=500, json={})

    await _refresh(hass, setup_integration)

    assert hass.states.get(ENTITY_ID).state == "unavailable"


async def test_options_set_the_polling_interval(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """The polling interval can be changed from the options."""
    entry = setup_integration
    assert entry.runtime_data.update_interval == timedelta(minutes=1)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 5}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"scan_interval": 5}
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.update_interval == timedelta(minutes=5)


def _fetches(aioclient_mock: AiohttpClientMocker, url: str) -> int:
    return sum(
        1 for call in aioclient_mock.mock_calls if call[0] == "GET" and str(call[1]) == url
    )


@pytest.mark.parametrize(
    ("disabled", "fetched"),
    [
        # Both entities of the list disabled: it is no longer polled
        (("todo.groceries", "calendar.groceries"), 0),
        # Its calendar is still in use
        (("todo.groceries",), 1),
    ],
)
async def test_disabled_list_is_not_polled(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    disabled: tuple[str, ...],
    fetched: int,
) -> None:
    """Disabling a list's entities is how to cut the number of requests."""
    for entity_id in disabled:
        entity_registry.async_update_entity(
            entity_id, disabled_by=er.RegistryEntryDisabler.USER
        )
    reset_api(aioclient_mock)
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data(TASK))

    await _refresh(hass, setup_integration)

    assert _fetches(aioclient_mock, PROJECT_DATA_URL) == fetched
    assert setup_integration.runtime_data.last_update_success


async def test_slow_list_does_not_block_the_others(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A list that times out is treated like any other failing list."""
    reset_api(aioclient_mock, projects=[PROJECT, CHORES])
    aioclient_mock.get(PROJECT_DATA_URL, exc=TimeoutError())
    aioclient_mock.get(CHORES_DATA_URL, json=CHORES_DATA)

    await _refresh(hass, setup_integration)

    assert hass.states.get(ENTITY_ID).state == "1"
    assert hass.states.get(CHORES_ENTITY_ID).state == "0"


async def test_change_refreshes_only_that_list(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Adding an item fetches its own list again, not every list."""
    reset_api(aioclient_mock, projects=[PROJECT, CHORES])
    aioclient_mock.get(PROJECT_DATA_URL, json=project_data(TASK))
    aioclient_mock.get(CHORES_DATA_URL, json=CHORES_DATA)
    await _refresh(hass, setup_integration)
    aioclient_mock.post(
        "https://api.ticktick.com/open/v1/task", json={**TASK, "id": "task2"}
    )
    before = aioclient_mock.call_count

    await hass.services.async_call(
        "todo",
        "add_item",
        {"item": "Bread"},
        target={"entity_id": ENTITY_ID},
        blocking=True,
    )

    # The create call and one fetch of Groceries
    assert aioclient_mock.call_count == before + 2
    assert _fetches(aioclient_mock, CHORES_DATA_URL) == 1
