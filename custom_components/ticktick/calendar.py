"""Calendars showing the TickTick tasks that have a due date, one per list."""

from datetime import date, datetime, timedelta

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


def _span(task: Task) -> tuple[date | datetime, date | datetime] | None:
    """Return when a task starts and ends as an event, or None without due date."""
    due = due_from_task(task)
    if due is None:
        return None
    start = min(start_from_task(task) or due, due)
    if isinstance(due, datetime):
        return start, due if due > start else start + DEFAULT_EVENT_DURATION
    # All-day events end on the day after their last day
    return start, due + timedelta(days=1)


def _as_local(value: date | datetime) -> datetime:
    """Return the moment a date or datetime stands for, in local time."""
    if isinstance(value, datetime):
        return dt_util.as_local(value)
    return dt_util.start_of_local_day(value)


def _event(task: Task, span: tuple[date | datetime, date | datetime]) -> CalendarEvent:
    return CalendarEvent(
        start=span[0],
        end=span[1],
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

    def _spans(self) -> list[tuple[Task, datetime, datetime]]:
        """Return each dated task with its local start and end.

        Building a CalendarEvent validates it, which is slow for thousands of
        tasks, so events are only built for the tasks that are asked for.
        """
        project_with_tasks = (self.coordinator.data or {}).get(self._project_id)
        tasks = (project_with_tasks.tasks if project_with_tasks else None) or ()
        return [
            (task, _as_local(span[0]), _as_local(span[1]))
            for task in tasks
            if (span := _span(task))
        ]

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""
        now = dt_util.now()
        upcoming = [item for item in self._spans() if item[2] > now]
        if not upcoming:
            return None
        task = min(upcoming, key=lambda item: item[1])[0]
        return _event(task, _span(task))

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the events that overlap the given time range."""
        return [
            _event(task, _span(task))
            for task, start, end in self._spans()
            if start < end_date and end > start_date
        ]
