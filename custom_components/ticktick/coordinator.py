"""DataUpdateCoordinator for the TickTick component."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, INBOX_ID
from .ticktick_api_python.models.project import Kind, Project
from .ticktick_api_python.models.project_with_tasks import ProjectWithTasks
from .ticktick_api_python.ticktick_api import TickTickAPIClient, TickTickAuthError

type TickTickConfigEntry = ConfigEntry[TickTickCoordinator]

# Seconds to wait for one answer from TickTick before giving up on it
REQUEST_TIMEOUT = 30

# The entity domains that show one TickTick list each
LIST_DOMAINS = ("todo", "calendar")

# TickTick leaves the inbox out of the project list, but serves it under this id
INBOX = Project(
    id=INBOX_ID,
    groupId=None,
    name="Inbox",
    color=None,
    sortOrder=0,
    closed=False,
    viewMode=None,
    permission=None,
    kind=Kind.TASK,
)


class TickTickCoordinator(DataUpdateCoordinator[dict[str, ProjectWithTasks]]):
    """Coordinator for updating task data from TickTick, keyed by project id."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        entry: ConfigEntry | None,
        update_interval: timedelta,
        api: TickTickAPIClient,
        access_token: str,
    ) -> None:
        """Initialize the TickTick coordinator."""
        super().__init__(
            hass,
            logger,
            config_entry=entry,
            name="TickTick",
            update_interval=update_interval,
        )
        self.api = api
        self.projects: dict[str, Project] = {}
        self.failing: set[str] = set()
        self.access_token = access_token

    async def _async_update_data(self) -> dict[str, ProjectWithTasks]:
        """Fetch the current projects and their tasks from the TickTick API."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                projects = await self.api.get_projects()
        except TickTickAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        # Fetched on every update, so lists added, renamed or deleted in
        # TickTick are picked up without a reload
        self.projects = {INBOX_ID: INBOX} | {project.id: project for project in projects}

        data: dict[str, ProjectWithTasks] = {}
        failed: dict[str, Exception] = {}
        wanted = [pid for pid in self.projects if self._is_wanted(pid)]
        # One request at a time: TickTick has no call for all lists at once and
        # refuses a burst of simultaneous requests (exceed_query_limit)
        for project_id in wanted:
            try:
                data[project_id] = await self._fetch_project(self.projects[project_id])
            except TickTickAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except Exception as err:  # noqa: BLE001
                failed[project_id] = err
                # One list failing should not take the others down: keep
                # showing what we last knew for it
                if self.data and project_id in self.data:
                    data[project_id] = self.data[project_id]

        if failed and len(failed) == len(wanted):
            raise UpdateFailed(
                f"Error communicating with API: {next(iter(failed.values()))!r}"
            )
        for project_id in failed.keys() - self.failing:
            self.logger.warning(
                "Could not update TickTick list %s, keeping its last known tasks: %r",
                self.projects[project_id].name,
                failed[project_id],
            )
        self.failing = set(failed)
        return data

    async def async_refresh_project(self, project_id: str | None) -> None:
        """Fetch one list again after a change to it, without polling the rest."""
        if project_id and project_id not in self.projects:
            # Tasks in the inbox carry its real id, which starts with "inbox"
            project_id = INBOX_ID if project_id.startswith(INBOX_ID) else None
        if project_id is None or self.data is None:
            await self.async_refresh()
            return
        try:
            fresh = await self._fetch_project(self.projects[project_id])
        except Exception as err:  # noqa: BLE001
            # The change itself went through; the next update will show it
            self.logger.warning(
                "Could not refresh TickTick list %s after a change: %r",
                self.projects[project_id].name,
                err,
            )
            return
        self.async_set_updated_data({**self.data, project_id: fresh})

    def _is_wanted(self, project_id: str) -> bool:
        """Return False for a list whose entities have all been disabled.

        Disabling a list's entities is how a user with many lists keeps the
        number of requests down.
        """
        registry = er.async_get(self.hass)
        unique_id = f"{self.config_entry.entry_id}-{project_id}"
        entities = [
            registry.async_get(entity_id)
            for domain in LIST_DOMAINS
            if (entity_id := registry.async_get_entity_id(domain, DOMAIN, unique_id))
        ]
        return not entities or any(not entity.disabled for entity in entities)

    async def _fetch_project(self, project: Project) -> ProjectWithTasks:
        """Fetch one project with its open tasks."""
        async with asyncio.timeout(REQUEST_TIMEOUT):
            response = await self.api.get_project_with_tasks(
                project.id, returnAsJson=True
            )
        return ProjectWithTasks.from_dict(response, project)
