"""Shared entity helpers for the TickTick integration."""

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, INBOX_ID
from .coordinator import TickTickConfigEntry, TickTickCoordinator
from .ticktick_api_python.models.task import Task


def ticktick_device_info(entry_id: str) -> DeviceInfo:
    """Return the device all entities of one TickTick account belong to."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="TickTick",
        manufacturer="TickTick",
        entry_type=DeviceEntryType.SERVICE,
    )


def parse_ticktick_datetime(value: Any) -> datetime | None:
    """Parse a TickTick timestamp such as 2026-10-26T04:00:00.000+0000."""
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        return dt_util.parse_datetime(str(value))


def _as_home_assistant_date(value: datetime, task: Task) -> date | datetime:
    """Return a date for an all-day task, in its own time zone; else the datetime."""
    if task.isAllDay:
        zone = dt_util.get_time_zone(task.timeZone) if task.timeZone else None
        return value.astimezone(zone or dt_util.get_default_time_zone()).date()
    return value


def due_from_task(task: Task) -> date | datetime | None:
    """Return the task's due date as Home Assistant expects it.

    All-day tasks become a date in the task's time zone; others an aware datetime.
    """
    # Sensors and calendars ask for this on every state update; parsing is the
    # costly part with thousands of tasks, so do it once per fetched task
    try:
        return task._ha_due
    except AttributeError:
        due = parse_ticktick_datetime(task.dueDate)
        task._ha_due = None if due is None else _as_home_assistant_date(due, task)
        return task._ha_due


def start_from_task(task: Task) -> date | datetime | None:
    """Return the task's start date, falling back to its due date."""
    try:
        return task._ha_start
    except AttributeError:
        start = parse_ticktick_datetime(task.startDate)
        task._ha_start = (
            due_from_task(task)
            if start is None
            else _as_home_assistant_date(start, task)
        )
        return task._ha_start


@callback
def async_setup_list_entities(
    hass: HomeAssistant,
    entry: TickTickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    domain: str,
    create: Callable[[TickTickCoordinator, str, str, str], Entity],
) -> None:
    """Keep one entity per TickTick list in `domain`, following TickTick.

    `create` is called with the coordinator, config entry id, project id and
    project name for each list that appears.
    """
    coordinator = entry.runtime_data
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}-"
    known: set[str] = set()

    @callback
    def _sync_lists() -> None:
        """Add an entity for each new project and drop those that are gone."""
        projects = coordinator.projects
        if new := projects.keys() - known:
            known.update(new)
            async_add_entities(
                create(coordinator, entry.entry_id, project_id, projects[project_id].name)
                for project_id in new
            )

        # An empty project list is more likely a hiccup than every list being
        # deleted at once; removing the entities would lose their settings
        if projects.keys() == {INBOX_ID}:
            return
        for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            project_id = reg_entry.unique_id.removeprefix(prefix)
            if reg_entry.domain == domain and project_id not in projects:
                registry.async_remove(reg_entry.entity_id)
                known.discard(project_id)

    _sync_lists()
    entry.async_on_unload(coordinator.async_add_listener(_sync_lists))
