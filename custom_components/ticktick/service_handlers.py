"""Service Handlers for TickTick Integration."""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .builders import build_items, build_reminders, build_repeat_flag
from .const import DOMAIN, PROJECT_ID, TASK_ID
from .coordinator import TickTickCoordinator
from .ticktick_api_python.models.project import Kind, ViewMode
from .ticktick_api_python.models.task import Task, TaskPriority

_LOGGER = logging.getLogger(__name__)

PROJECT_FIELDS = {
    "color": cv.string,
    "sortOrder": vol.Coerce(int),
    "viewMode": vol.In([mode.value for mode in ViewMode]),
    "kind": vol.In([kind.value for kind in Kind]),
}
PROJECT_SCHEMA = vol.Schema({vol.Required(PROJECT_ID): cv.string})
CREATE_PROJECT_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        **{vol.Optional(field): check for field, check in PROJECT_FIELDS.items()},
    }
)
UPDATE_PROJECT_SCHEMA = PROJECT_SCHEMA.extend(
    {
        vol.Optional("name"): cv.string,
        **{vol.Optional(field): check for field, check in PROJECT_FIELDS.items()},
    }
)


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register TickTick services."""

    # === Task Scope ===
    hass.services.async_register(
        DOMAIN,
        "get_task",
        _create_handler("get_task", PROJECT_ID, TASK_ID),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "create_task",
        _create_handler(
            "create_task", *(Task.get_arg_names()), type=Task, refresh=True
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "complete_task",
        _create_handler("complete_task", PROJECT_ID, TASK_ID, refresh=True),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "delete_task",
        _create_handler("delete_task", PROJECT_ID, TASK_ID, refresh=True),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "update_task",
        _handle_update_task,
        supports_response=SupportsResponse.OPTIONAL,
    )

    # === Project Scope ===
    hass.services.async_register(
        DOMAIN,
        "get_projects",
        _create_handler("get_projects"),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_project",
        _create_project_handler("get_project", PROJECT_ID),
        schema=PROJECT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_detailed_project",
        _create_project_handler("get_project_with_tasks", PROJECT_ID),
        schema=PROJECT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "create_project",
        _create_project_handler("create_project", "name", *PROJECT_FIELDS, reload=True),
        schema=CREATE_PROJECT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "update_project",
        _create_project_handler(
            "update_project", PROJECT_ID, "name", *PROJECT_FIELDS, reload=True
        ),
        schema=UPDATE_PROJECT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "delete_project",
        _create_project_handler("delete_project", PROJECT_ID, reload=True),
        schema=PROJECT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


def _create_project_handler(
    method_name: str, *arg_names: str, reload: bool = False
) -> Callable:
    """Create a handler for a project endpoint; only given fields are passed on."""

    async def handler(call: ServiceCall) -> dict[str, Any]:
        coordinator = _get_coordinator(call.hass)
        args = {arg: call.data[arg] for arg in arg_names if arg in call.data}
        try:
            response = await getattr(coordinator.api, method_name)(
                **args, returnAsJson=True
            )
        except Exception as e:
            raise HomeAssistantError(str(e)) from e

        if reload:
            entry = coordinator.config_entry
            if method_name == "delete_project":
                # The list is gone for good, so don't leave its entity behind
                registry = er.async_get(call.hass)
                unique_id = f"{entry.entry_id}-{call.data[PROJECT_ID]}"
                if entity_id := registry.async_get_entity_id("todo", DOMAIN, unique_id):
                    registry.async_remove(entity_id)
            # The to-do lists are created at setup, so set up again to add,
            # rename or drop the list this call changed
            call.hass.config_entries.async_schedule_reload(entry.entry_id)
        return {"data": response}

    return handler


def _get_coordinator(hass: HomeAssistant) -> TickTickCoordinator:
    """Return the coordinator of the loaded TickTick config entry."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("TickTick is not set up or failed to load")
    return entries[0].runtime_data


async def _handle_update_task(call: ServiceCall) -> dict[str, Any]:
    """Handle the update_task service call."""
    coordinator = _get_coordinator(call.hass)
    client = coordinator.api
    project_id = call.data.get(PROJECT_ID)
    task_id = call.data.get(TASK_ID)

    if not project_id or not task_id:
        raise ServiceValidationError(f"Both {PROJECT_ID} and {TASK_ID} are required")

    try:
        # First, get the existing task
        existing_task_response = await client.get_task(
            project_id, task_id, returnAsJson=True
        )

        # Create a Task object from the existing task data
        existing_task = Task.from_dict(existing_task_response)
        _LOGGER.debug("Retrieved existing task: %s", existing_task.title)

        # Update only the fields that are provided in the service call
        if "title" in call.data:
            existing_task.title = call.data.get("title")
            _LOGGER.debug("Updating task title to: %s", existing_task.title)

        # Handle both desc and content fields
        if "content" in call.data and "desc" in call.data:
            _LOGGER.warning(
                "Both 'content' and 'desc' fields provided. Using 'content' field."
            )
            existing_task.content = call.data.get("content")
            existing_task.desc = call.data.get("desc")
            _LOGGER.debug("Updating task content to: %s", existing_task.content)
        elif "content" in call.data:
            existing_task.content = call.data.get("content")
            _LOGGER.debug("Updating task content to: %s", existing_task.content)
        elif "desc" in call.data:
            existing_task.content = call.data.get("desc")
            existing_task.desc = call.data.get("desc")
            _LOGGER.debug(
                "Updating task content and desc to: %s", existing_task.content
            )

        if "dueDate" in call.data:
            due_date = call.data.get("dueDate")
            due_date_time_zone = call.data.get("timeZone")

            if isinstance(due_date, str):
                existing_task.dueDate = _sanitize_date(due_date, due_date_time_zone)
            else:
                existing_task.dueDate = due_date
            _LOGGER.debug("Updated task due date to: %s", existing_task.dueDate)

        # Handle additional fields
        if "isAllDay" in call.data:
            existing_task.isAllDay = call.data.get("isAllDay")
            _LOGGER.debug("Updating task isAllDay to: %s", existing_task.isAllDay)

        if "startDate" in call.data:
            start_date = call.data.get("startDate")
            start_date_time_zone = call.data.get("timeZone")

            if isinstance(start_date, str):
                existing_task.startDate = _sanitize_date(
                    start_date, start_date_time_zone
                )
            else:
                existing_task.startDate = start_date
            _LOGGER.debug("Updated task start date to: %s", existing_task.startDate)

        if "repeatFlag" in call.data:
            existing_task.repeatFlag = build_repeat_flag(call.data.get("repeatFlag"))
            _LOGGER.debug("Updating task repeat flag to: %s", existing_task.repeatFlag)

        if "reminders" in call.data:
            existing_task.reminders = build_reminders(call.data.get("reminders"))
            _LOGGER.debug("Updating task reminders to: %s", existing_task.reminders)

        if "items" in call.data:
            # Replaces the whole list; pass a subtask's id to keep that subtask
            existing_task.items = build_items(call.data.get("items"))
            _LOGGER.debug("Updating task to %s subtasks", len(existing_task.items))

        if "priority" in call.data:
            priority = call.data.get("priority")
            if isinstance(priority, str):
                try:
                    existing_task.priority = TaskPriority[priority]
                    _LOGGER.debug(
                        "Updating task priority to: %s", existing_task.priority
                    )
                except KeyError:
                    _LOGGER.warning("Invalid priority value: %s. Ignoring.", priority)
            else:
                existing_task.priority = priority
                _LOGGER.debug("Updating task priority to: %s", existing_task.priority)

        if "sortOrder" in call.data:
            existing_task.sortOrder = call.data.get("sortOrder")
            _LOGGER.debug("Updating task sort order to: %s", existing_task.sortOrder)

        # Update the task in TickTick
        response = await client.update_task(existing_task, returnAsJson=True)
    except ValueError as e:
        raise ServiceValidationError(str(e)) from e
    except Exception as e:
        hint = await _project_hint(coordinator, project_id)
        raise HomeAssistantError(f"Error updating task: {e}{hint}") from e

    await coordinator.async_refresh()
    return {"data": response}


T = TypeVar("T")


def _create_handler(
    method_name: str,
    *arg_names: str,
    type: type[T] | None = None,
    refresh: bool = False,
) -> Callable:
    """Create a reusable handler function for TickTick API endpoints."""

    async def handler(call: ServiceCall) -> dict[str, Any]:
        """Return a generic handler for TickTick API endpoints."""

        coordinator = _get_coordinator(call.hass)
        client_method = getattr(coordinator.api, method_name)
        args = {arg: call.data.get(arg) for arg in arg_names}
        try:
            response = None
            if type == Task:
                if "dueDate" in args and isinstance(args["dueDate"], str):
                    args["dueDate"] = _sanitize_date(args["dueDate"], args["timeZone"])
                if "startDate" in args and isinstance(args["startDate"], str):
                    args["startDate"] = _sanitize_date(
                        args["startDate"], args["timeZone"]
                    )
                if "priority" in args and isinstance(args["priority"], str):
                    try:
                        args["priority"] = TaskPriority[args["priority"]]
                    except Exception:
                        args["priority"] = None
                args["reminders"] = build_reminders(args.get("reminders"))
                args["repeatFlag"] = build_repeat_flag(args.get("repeatFlag"))
                args["items"] = build_items(args.get("items"))
                instance = type(**args)
                response = await client_method(instance, returnAsJson=True)
            else:
                response = await client_method(**args, returnAsJson=True)
        except ValueError as e:
            raise ServiceValidationError(str(e)) from e
        except Exception as e:
            hint = await _project_hint(coordinator, args.get(PROJECT_ID))
            raise HomeAssistantError(f"{e}{hint}") from e

        if refresh:
            # Show the change in the to-do lists right away
            await coordinator.async_refresh()
        return {"data": response}

    return handler


async def _project_hint(coordinator: TickTickCoordinator, project_id: Any) -> str:
    """Explain a failed call that used a project ID TickTick does not know.

    TickTick answers an unknown project ID with a bare 500, which says nothing.
    """
    if not project_id:
        return ""
    try:
        projects = await coordinator.api.get_projects(returnAsJson=True)
    except Exception:
        return ""
    # The inbox is a valid project that TickTick leaves out of the project list
    if str(project_id).startswith("inbox") or any(
        project.get("id") == project_id for project in projects
    ):
        return ""
    return (
        f". Project ID {project_id!r} is not one of your TickTick projects; "
        "run ticktick.get_projects to find the right ID"
    )


def _sanitize_date(date: str, timeZone: str | None) -> str:
    """Sanitize a date string to the format expected by TickTick API."""
    naive_dt = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")

    if timeZone:
        zone_info = ZoneInfo(timeZone)
    else:
        zone_info = dt_util.get_default_time_zone()

    aware_dt = naive_dt.replace(tzinfo=zone_info)

    return aware_dt.strftime("%Y-%m-%dT%H:%M:%S%z")
