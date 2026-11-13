from .project import Project
from .task import Task


class ProjectWithTasks:
    """ProjectWithTasks Class for TickTick."""

    def __init__(
        self,
        project: Project,
        tasks: list[Task] | None,
        columns: any,  # TODO
    ) -> None:
        """Intialize a ProjectWithTasks object."""
        self.project = project
        self.tasks = tasks
        self.columns = columns

    @staticmethod
    def from_dict(data: dict, project: Project | None = None) -> "ProjectWithTasks":
        """Create a ProjectWithTasks instance from a dictionary.

        `project` is used when the response carries no project, as for the inbox.
        """
        if not data:
            # TickTick answers a project it does not know with an empty object
            raise ValueError("TickTick returned no data for the project")
        if data.get("project"):
            project = Project.from_dict(data["project"])
        if project is None:
            raise ValueError("TickTick returned tasks without a project")
        tasks = (
            [
                Task.from_dict(task)
                for task in data.get("tasks", [])
                if task.get("status") in (0, "0", None) # Filtering out status 1 and 2 as it's not supported in HomeAssistant
            ]
            if data.get("tasks")
            else None
        )
        columns = data.get(
            "columns"
        )  # TODO: Update with the appropriate logic once columns type is defined

        return ProjectWithTasks(
            project=project,
            tasks=tasks,
            columns=columns,
        )
