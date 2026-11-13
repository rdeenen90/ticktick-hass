"""DataUpdateCoordinator for the TickTick component."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import INBOX_ID
from .ticktick_api_python.models.project import Kind, Project
from .ticktick_api_python.models.project_with_tasks import ProjectWithTasks
from .ticktick_api_python.ticktick_api import TickTickAPIClient, TickTickAuthError

type TickTickConfigEntry = ConfigEntry[TickTickCoordinator]

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
        self._failing: set[str] = set()
        self.access_token = access_token

    async def _async_update_data(self) -> dict[str, ProjectWithTasks]:
        """Fetch the current projects and their tasks from the TickTick API."""
        try:
            projects = await self.api.get_projects()
        except TickTickAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        # Fetched on every update, so lists added, renamed or deleted in
        # TickTick are picked up without a reload
        self.projects = {INBOX_ID: INBOX} | {project.id: project for project in projects}

        results = await asyncio.gather(
            *(self._fetch_project(project) for project in self.projects.values()),
            return_exceptions=True,
        )

        data: dict[str, ProjectWithTasks] = {}
        failed: dict[str, BaseException] = {}
        for project_id, result in zip(self.projects, results):
            if isinstance(result, TickTickAuthError):
                raise ConfigEntryAuthFailed(str(result)) from result
            if isinstance(result, BaseException):
                failed[project_id] = result
                # One list failing should not take the others down: keep
                # showing what we last knew for it
                if self.data and project_id in self.data:
                    data[project_id] = self.data[project_id]
                continue
            data[project_id] = result

        if failed and len(failed) == len(self.projects):
            raise UpdateFailed(
                f"Error communicating with API: {next(iter(failed.values()))}"
            )
        for project_id in failed.keys() - self._failing:
            self.logger.warning(
                "Could not update TickTick list %s, keeping its last known tasks: %s",
                self.projects[project_id].name,
                failed[project_id],
            )
        self._failing = set(failed)
        return data

    async def _fetch_project(self, project: Project) -> ProjectWithTasks:
        """Fetch one project with its open tasks."""
        response = await self.api.get_project_with_tasks(project.id, returnAsJson=True)
        return ProjectWithTasks.from_dict(response, project)
