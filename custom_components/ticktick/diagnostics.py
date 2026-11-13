"""Diagnostics for the TickTick integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import TickTickConfigEntry

TO_REDACT = {"token"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TickTickConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Tasks and list names are personal, so only counts and settings are included.
    """
    coordinator = entry.runtime_data
    lists = []
    for project_id, project in coordinator.projects.items():
        project_with_tasks = (coordinator.data or {}).get(project_id)
        tasks = (project_with_tasks.tasks if project_with_tasks else None) or []
        lists.append(
            {
                "kind": project.kind.value if project.kind else None,
                "view_mode": project.viewMode.value if project.viewMode else None,
                "fetched": project_with_tasks is not None,
                "failing": project_id in coordinator.failing,
                "open_tasks": len(tasks),
                "tasks_with_due_date": sum(1 for task in tasks if task.dueDate),
                "all_day_tasks": sum(1 for task in tasks if task.isAllDay),
                "checklist_tasks": sum(1 for task in tasks if task.kind == "CHECKLIST"),
            }
        )

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": coordinator.update_interval.total_seconds(),
        },
        "lists": lists,
    }
