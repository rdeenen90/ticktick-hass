"""Sensors counting the TickTick tasks that are open, overdue or due today."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import TickTickConfigEntry, TickTickCoordinator
from .entity import due_from_task, ticktick_device_info
from .ticktick_api_python.models.task import Task

# Task titles in the attributes are for notifications, not for a full export
MAX_TASKS_IN_ATTRIBUTES = 20


def _is_overdue(task: Task, now: datetime) -> bool:
    """Return whether the task's due moment, or its due day, has passed."""
    due = due_from_task(task)
    if due is None:
        return False
    if isinstance(due, datetime):
        return due < now
    return due < now.date()


def _is_due_today(task: Task, now: datetime) -> bool:
    """Return whether the task is due today, whether or not its time has passed."""
    due = due_from_task(task)
    if due is None:
        return False
    if isinstance(due, datetime):
        due = dt_util.as_local(due).date()
    return due == now.date()


@dataclass(frozen=True, kw_only=True)
class TickTickSensorDescription(SensorEntityDescription):
    """Describes a TickTick task count sensor."""

    matches: Callable[[Task, datetime], bool]
    # Whether the matching tasks are listed in the attributes
    list_tasks: bool = True


SENSORS = (
    TickTickSensorDescription(
        key="overdue", translation_key="overdue_tasks", matches=_is_overdue
    ),
    TickTickSensorDescription(
        key="due_today", translation_key="tasks_due_today", matches=_is_due_today
    ),
    TickTickSensorDescription(
        key="open",
        translation_key="open_tasks",
        matches=lambda task, now: True,
        list_tasks=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TickTickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TickTick sensor platform config entry."""
    async_add_entities(
        TickTickTaskCountSensor(entry.runtime_data, entry.entry_id, description)
        for description in SENSORS
    )


class TickTickTaskCountSensor(CoordinatorEntity[TickTickCoordinator], SensorEntity):
    """Counts the open tasks across all lists that match a condition."""

    entity_description: TickTickSensorDescription
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "tasks"
    # The per-list counts and task titles change too often to be worth recording
    _unrecorded_attributes = frozenset({"lists", "tasks"})

    def __init__(
        self,
        coordinator: TickTickCoordinator,
        config_entry_id: str,
        description: TickTickSensorDescription,
    ) -> None:
        """Initialize TickTickTaskCountSensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry_id}-{description.key}"
        self._attr_device_info = ticktick_device_info(config_entry_id)

    def _matching(self) -> list[tuple[str, Task]]:
        """Return the matching tasks with the name of their list."""
        now = dt_util.now()
        return [
            (project_with_tasks.project.name, task)
            for project_with_tasks in (self.coordinator.data or {}).values()
            for task in project_with_tasks.tasks or ()
            if self.entity_description.matches(task, now)
        ]

    @property
    def native_value(self) -> int:
        """Return the number of matching tasks."""
        return len(self._matching())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the count per list and, for the dated sensors, the tasks."""
        matching = self._matching()
        lists: dict[str, int] = {}
        for list_name, _ in matching:
            lists[list_name] = lists.get(list_name, 0) + 1
        attributes: dict[str, Any] = {"lists": lists}
        if self.entity_description.list_tasks:
            attributes["tasks"] = [
                {
                    "title": task.title,
                    "list": list_name,
                    "due": due_from_task(task).isoformat(),
                }
                for list_name, task in matching[:MAX_TASKS_IN_ATTRIBUTES]
            ]
        return attributes
