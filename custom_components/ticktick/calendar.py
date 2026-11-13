"""Calendars showing the TickTick tasks that have a due date, one per list."""

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import TickTickConfigEntry, TickTickCoordinator
from .entity import (
    async_setup_list_entities,
    due_from_task,
    start_from_task,
)
from .ticktick_api_python.models.task import Task

# How long a task with only a due time is shown for
DEFAULT_EVENT_DURATION = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TickTickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TickTick calendar platform config entry."""
    async_setup_list_entities(
        hass, entry, async_add_entities, "calendar", TickTickCalendarEntity
    )


def _event_from_task(task: Task) -> CalendarEvent | None:
    """Return the calendar event for a task, or None if it has no due date."""
    due = due_from_task(task)
    if due is None:
        return None
    start = min(start_from_task(task) or due, due)
    if isinstance(due, datetime):
        end = due if due > start else start + DEFAULT_EVENT_DURATION
    else:
        # All-day events end on the day after their last day
        end = due + timedelta(days=1)
    return CalendarEvent(
        start=start,
        end=end,
        summary=task.title,
        description=task.content or task.desc or None,
        uid=task.id,
    )


class TickTickCalendarEntity(CoordinatorEntity[TickTickCoordinator], CalendarEntity):
    """A calendar with the dated tasks of one TickTick list."""

    def __init__(
        self,
        coordinator: TickTickCoordinator,
        config_entry_id: str,
        project_id: str,
        project_name: str,
    ) -> None:
        """Initialize TickTickCalendarEntity."""
        super().__init__(coordinator=coordinator)
        self._project_id = project_id
        self._attr_unique_id = f"{config_entry_id}-{project_id}"
        self._attr_name = project_name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if project := self.coordinator.projects.get(self._project_id):
            # Follow a rename in TickTick
            self._attr_name = project.name
        super()._handle_coordinator_update()

    def _events(self) -> list[CalendarEvent]:
        project_with_tasks = (self.coordinator.data or {}).get(self._project_id)
        tasks = (project_with_tasks.tasks if project_with_tasks else None) or ()
        return [event for task in tasks if (event := _event_from_task(task))]

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""
        now = dt_util.now()
        upcoming = [event for event in self._events() if event.end_datetime_local > now]
        return min(upcoming, key=lambda event: event.start_datetime_local, default=None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the events that overlap the given time range."""
        return [
            event
            for event in self._events()
            if event.start_datetime_local < end_date
            and event.end_datetime_local > start_date
        ]
