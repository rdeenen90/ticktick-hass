<p align="center">
  <img src="custom_components/ticktick/brand/logo.png" alt="TickTick" width="300">
</p>

<h1 align="center">TickTick for Home Assistant</h1>

<p align="center">
  Your TickTick lists as Home Assistant to-do lists, with services to manage tasks and projects from automations.
</p>

<p align="center">
  <a href="https://github.com/rdeenen90/ticktick-hass/releases/latest"><img src="https://img.shields.io/github/v/release/rdeenen90/ticktick-hass?style=flat-square" alt="Latest release"></a>
  <a href="https://github.com/rdeenen90/ticktick-hass/actions/workflows/validate.yaml"><img src="https://img.shields.io/github/actions/workflow/status/rdeenen90/ticktick-hass/validate.yaml?branch=main&style=flat-square&label=checks" alt="Checks"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2026.10%2B-41BDF5?style=flat-square&logo=homeassistant&logoColor=white" alt="Home Assistant 2026.10 or newer">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/rdeenen90/ticktick-hass?style=flat-square" alt="License"></a>
</p>

---

This integration uses the [TickTick Open API](https://developer.ticktick.com/docs#/openapi). Every TickTick list becomes a [to-do list](https://www.home-assistant.io/integrations/todo/) entity, and the `ticktick.*` services give automations full access to tasks and projects.

## Features

- **To-do lists:** every TickTick list and the inbox, kept in step with TickTick as lists are added, renamed or deleted; add, rename, complete and delete tasks, with due dates (all-day or timed) and descriptions
- **Calendars:** a calendar per list with the tasks that have a due date
- **Sensors:** overdue, due today and open task counts across all lists
- **Task services:** get, create, update, complete and delete, including subtasks, reminders, repeat rules and priority
- **Project services:** get, create, update and delete lists
- **Re-authentication:** when the TickTick token expires, Home Assistant asks you to sign in again instead of breaking

## Installation

1. Go to [TickTick Developer](https://developer.ticktick.com/manage) and click `New App`.
2. Name the app and set `OAuth redirect URL` to `https://my.home-assistant.io/redirect/oauth`.
3. In Home Assistant, add this repository as a custom repository under Settings → Marketplace (HACS on Home Assistant older than 2026.11) and download the TickTick integration.
4. Add the TickTick integration under Settings → Devices & services, and enter the client ID and secret of your TickTick app when asked.
5. Each TickTick list now shows up as a to-do list.

If you don't want every list in Home Assistant, disable the ones you don't need in the entities list.

## Services

### Tasks

| Service | What it does |
|---|---|
| `ticktick.get_task` | Returns one task |
| `ticktick.create_task` | Creates a task |
| `ticktick.update_task` | Changes only the fields you pass |
| `ticktick.complete_task` | Marks a task as done |
| `ticktick.delete_task` | Deletes a task |

Every task service needs to know the list, and most need a task:

- **List:** pass `list` with a TickTick to-do list entity, or `projectId` with the ID from `ticktick.get_projects`. The inbox is `todo.inbox`, or `projectId: inbox`.
- **Task:** pass `taskTitle` with the title of an open task in that list (it must match exactly one, ignoring case), or `taskId` with the ID from `ticktick.get_detailed_project`.

```yaml
action: ticktick.complete_task
data:
  list: todo.groceries
  taskTitle: Milk
```

```yaml
action: ticktick.create_task
data:
  list: todo.groceries
  title: Weekly shop
  dueDate: "2026-11-20 18:00:00"
  priority: HIGH
  items:
    - Milk
    - title: Bread
      completed: true
  reminders:
    - on time
    - 1 hour
  repeatFlag: weekly
```

- **Subtasks (`items`):** a list of titles, or objects with `title`, `completed` and `id`. On `update_task` the list replaces the existing subtasks; pass a subtask's `id` to keep it.
- **Reminders (`reminders`):** a time before the task is due (`30 minutes`, `2 hours`, `1 day`), `on time`, `HH:MM` on the day of an all-day task, or a raw trigger such as `TRIGGER:P0DT9H0M0S`.
- **Repeat (`repeatFlag`):** `daily`, `weekly`, `monthly`, `yearly`, `weekdays`, `every 2 weeks`, or a raw rule such as `RRULE:FREQ=DAILY;INTERVAL=1`.
- **Emptying a field:** in `update_task`, pass an empty value to remove something: `dueDate: null`, `reminders: []`, `items: []`, `repeatFlag: ""` or `content: ""`. Removing the due date also removes the start date, reminders and repeat, as in the TickTick app.

### Projects

| Service | What it does |
|---|---|
| `ticktick.get_projects` | Returns all projects |
| `ticktick.get_project` | Returns one project |
| `ticktick.get_detailed_project` | Returns one project with its tasks |
| `ticktick.create_project` | Creates a project |
| `ticktick.update_project` | Changes only the fields you pass |
| `ticktick.delete_project` | Deletes a project and all its tasks |

Project services that take a project accept `list` or `projectId`, like the task services. Creating, updating or deleting a project updates the to-do lists right away.

## Calendars and sensors

Each list also has a **calendar** entity, such as `calendar.groceries`, with its tasks that have a due date. An all-day task is an all-day event, a task with a start and a due time runs between them, and a task with only a due time is shown for half an hour. Disable the calendars you don't need in the entities list.

Three **sensors** count tasks across all lists:

| Sensor | Counts |
|---|---|
| `sensor.ticktick_overdue_tasks` | Tasks whose due time, or due day, has passed |
| `sensor.ticktick_tasks_due_today` | Tasks due today, including ones whose time has already passed |
| `sensor.ticktick_open_tasks` | All open tasks |

Each has a `lists` attribute with the count per list. The first two also have a `tasks` attribute with up to 20 tasks (title, list and due date), which is handy in notifications:

```yaml
action: notify.notify
data:
  message: >-
    Overdue: {{ state_attr('sensor.ticktick_overdue_tasks', 'tasks')
    | map(attribute='title') | join(', ') }}
```

## Options

Under Settings → Devices & services → TickTick → Configure you can set the **polling interval** (1 to 60 minutes, default 1).

## Many lists or tasks

TickTick has no way to fetch all lists at once, so each update makes one request per list, plus one for the list of projects. The requests are sent one at a time, because TickTick refuses a burst of them (`exceed_query_limit`). If you have many lists:

- **Disable the lists you don't need.** A list whose to-do list and calendar entities are both disabled is not fetched at all. It is also left out of the sensors.
- **Raise the polling interval** under Options.

A change made from Home Assistant only fetches the list it was made in.

## Known limitations

- Lists are polled, so changes made in the TickTick app take up to one polling interval to appear. That includes lists that are added, renamed or deleted there.
- A completed task cannot be reopened from Home Assistant, because TickTick's API does not return completed tasks.
- If one list cannot be fetched, it keeps showing its last known tasks while the other lists update.
- Sensors and calendars are recalculated on each update, so "overdue" can lag by up to one polling interval.
- A task with a start that differs from its due date cannot be created through the services: TickTick's API stores the due date as the start too. Such a time range has to be set in the TickTick app.

## Troubleshooting

To report a problem, download the diagnostics from Settings → Devices & services → TickTick (three-dot menu → Download diagnostics) and attach them to an [issue](https://github.com/rdeenen90/ticktick-hass/issues). They contain counts and settings only: no token, task titles or list names.

## Development

Everything runs in Docker, so no local Python is needed.

- **Tests and lint:** `bash scripts/test.sh` runs `ruff` and `pytest` in a container, the same checks as CI.
- **Devcontainer:** open the repository in VS Code and choose "Reopen in Container" (or use GitHub Codespaces). Tests then run with plain `pytest`.
- **Try it in Home Assistant:** inside the devcontainer, `bash scripts/develop.sh` starts a throwaway Home Assistant on http://localhost:8123 with the integration loaded. Its data lives in `./config`, which is not committed.

### Releasing

Set the new `version` in `custom_components/ticktick/manifest.json` and add a `## <version>` section to `CHANGELOG.md`. When that reaches `main` and the checks pass, CI publishes the GitHub release with that section as its notes. The checks fail if the changelog section is missing.

## Support

If this integration is useful to you, you can [buy me a coffee or beer](https://paypal.me/rdeenen90) 🍻

## Credits

This is a fork of [Hantick/ticktick-home-assistant](https://github.com/Hantick/ticktick-home-assistant), updated for current Home Assistant releases and extended. Thanks to Hantick for the original integration, and to the contributors whose upstream pull requests are included here. If you'd like to thank the original author, you can [buy them a coffee or beer](https://paypal.me/hantick).
