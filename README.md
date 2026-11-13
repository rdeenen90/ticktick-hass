<p align="center">
  <img src="custom_components/ticktick/brand/logo.png" alt="TickTick" width="300">
</p>

<h1 align="center">TickTick for Home Assistant</h1>

<p align="center">
  Your TickTick lists as Home Assistant to-do lists, with services to manage tasks and projects from automations.
</p>

<p align="center">
  <a href="https://github.com/rdeenen90/ticktick-hass/releases/latest"><img src="https://img.shields.io/github/v/release/rdeenen90/ticktick-hass?style=flat-square" alt="Latest release"></a>
  <a href="https://github.com/rdeenen90/ticktick-hass/actions/workflows/validate.yaml"><img src="https://img.shields.io/github/actions/workflow/status/rdeenen90/ticktick-hass/validate.yaml?branch=main&style=flat-square&label=tests" alt="Tests"></a>
  <a href="https://github.com/rdeenen90/ticktick-hass/actions/workflows/hassfest.yml"><img src="https://img.shields.io/github/actions/workflow/status/rdeenen90/ticktick-hass/hassfest.yml?branch=main&style=flat-square&label=hassfest" alt="hassfest"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2026.10%2B-41BDF5?style=flat-square&logo=homeassistant&logoColor=white" alt="Home Assistant 2026.10 or newer">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/rdeenen90/ticktick-hass?style=flat-square" alt="License"></a>
</p>

---

This integration uses the [TickTick Open API](https://developer.ticktick.com/docs#/openapi). Every TickTick list becomes a [to-do list](https://www.home-assistant.io/integrations/todo/) entity, and the `ticktick.*` services give automations full access to tasks and projects.

## Features

- **To-do lists:** add, rename, complete and delete tasks from Home Assistant, with due dates (all-day or timed) and descriptions
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

Task services need a `projectId`, and most need a `taskId`. `ticktick.get_projects` lists the project IDs, and `ticktick.get_detailed_project` returns a project with its tasks and their IDs.

```yaml
action: ticktick.create_task
data:
  projectId: 6987a8plg0rad90bc38b672f
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

### Projects

| Service | What it does |
|---|---|
| `ticktick.get_projects` | Returns all projects |
| `ticktick.get_project` | Returns one project |
| `ticktick.get_detailed_project` | Returns one project with its tasks |
| `ticktick.create_project` | Creates a project |
| `ticktick.update_project` | Changes only the fields you pass |
| `ticktick.delete_project` | Deletes a project and all its tasks |

Creating, updating or deleting a project reloads the integration, so the matching to-do list is added, renamed or removed right away.

## Known limitations

- Lists are polled once a minute, so changes made in the TickTick app can take up to a minute to appear.
- A list created in the TickTick app only appears after the integration is reloaded.
- A completed task cannot be reopened from Home Assistant, because TickTick's API does not return completed tasks.

## Development

Everything runs in Docker, so no local Python is needed.

- **Tests and lint:** `bash scripts/test.sh` runs `ruff` and `pytest` in a container, the same checks as CI.
- **Devcontainer:** open the repository in VS Code and choose "Reopen in Container" (or use GitHub Codespaces). Tests then run with plain `pytest`.
- **Try it in Home Assistant:** inside the devcontainer, `bash scripts/develop.sh` starts a throwaway Home Assistant on http://localhost:8123 with the integration loaded. Its data lives in `./config`, which is not committed.

## Support

If this integration is useful to you, you can [buy me a coffee or beer](https://paypal.me/rdeenen90) 🍻

## Credits

This is a fork of [Hantick/ticktick-home-assistant](https://github.com/Hantick/ticktick-home-assistant), updated for current Home Assistant releases and extended. Thanks to Hantick for the original integration, and to the contributors whose upstream pull requests are included here. If you'd like to thank the original author, you can [buy them a coffee or beer](https://paypal.me/hantick).
