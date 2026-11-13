# Changelog

Each release has a section here; its text becomes the release notes on GitHub.

## 2.6.0

Adds calendars, task count sensors and diagnostics. Requires Home Assistant 2026.10 or newer.

### New

- **Calendars.** Each TickTick list, and the inbox, has a calendar entity showing its tasks that have a due date. An all-day task is an all-day event; a task with a start and a due time runs between them; a task with only a due time is shown for half an hour. Calendars follow TickTick like the to-do lists do.
- **Sensors.** Three sensors count tasks across all lists: `sensor.ticktick_overdue_tasks`, `sensor.ticktick_tasks_due_today` and `sensor.ticktick_open_tasks`. Their `lists` attribute holds the count per list, and the first two also list up to 20 matching tasks with title, list and due date, for use in notifications.
- **Diagnostics.** Download diagnostics from the integration's page to attach to a bug report. They contain counts and settings only: no token, task titles or list names.

### Changes in behaviour

- A calendar entity is created for every list. Disable the ones you don't want in the entities list.
- "Due today" includes a task whose time has already passed today; such a task is also counted as overdue.

### Development

- Releases are published by CI: merging a new `version` in `manifest.json` to `main` publishes a release with that version's section of `CHANGELOG.md` as its notes.

## 2.5.0

Makes the integration follow TickTick more closely and the services easier to use. Requires Home Assistant 2026.10 or newer.

### Robustness

- **Lists follow TickTick.** A list added, renamed or deleted in the TickTick app is picked up on the next update, without a reload. A deleted list loses its entity; a renamed one keeps its entity ID.
- **One failing list no longer breaks the rest.** It keeps showing its last known tasks while the other lists update.
- **Polling interval option.** Settings → Devices & services → TickTick → Configure, 1 to 60 minutes (default 1). Raise it if you have many lists and run into TickTick's rate limit.

### Usability

- **Pick a list instead of an ID.** Task and project services accept `list` with a TickTick to-do list entity, as an alternative to `projectId`.
- **Pick a task by title.** Task services accept `taskTitle`, as an alternative to `taskId`. It must match exactly one open task in the list, ignoring case.
- **Inbox.** The TickTick inbox is now a to-do list (`todo.inbox`, or `projectId: inbox`).
- **Emptying fields.** Removing a due date or description in Home Assistant now removes it in TickTick. In `ticktick.update_task`, `dueDate: null`, `reminders: []`, `items: []`, `repeatFlag: ""` and `content: ""` empty that field.

```yaml
action: ticktick.complete_task
data:
  list: todo.groceries
  taskTitle: Milk
```

### Changes in behaviour

- Each update makes two more requests than before: the project list and the inbox.
- Creating, updating or deleting a project through the services refreshes the lists; it no longer reloads the integration.
- Removing a task's due date also removes its reminders and repeat rule, as in the TickTick app.
- This release also carries the `categories` entry in the manifest (calendars and to-dos).


## 2.4.0

Completes the README's original to-do list: subtasks, and friendlier reminders and repeat rules. Requires Home Assistant 2026.10 or newer.

### New in the task services

`ticktick.create_task` and `ticktick.update_task` now accept:

- **Subtasks (`items`):** a list of titles, or objects with `title`, `completed` and `id`. On update the list replaces the existing subtasks; pass a subtask's `id` to keep it.
- **Reminders (`reminders`):** a time before the task is due (`30 minutes`, `2 hours`, `1 day`), `on time`, `HH:MM` on the day of an all-day task, or a raw trigger such as `TRIGGER:P0DT9H0M0S` as before.
- **Repeat (`repeatFlag`):** `daily`, `weekly`, `monthly`, `yearly`, `weekdays`, `every 2 weeks`, or a raw rule such as `RRULE:FREQ=DAILY;INTERVAL=1` as before.

```yaml
action: ticktick.create_task
data:
  projectId: <an id from ticktick.get_projects>
  title: Weekly shop
  dueDate: "2026-11-20 18:00:00"
  items:
    - Milk
    - title: Bread
      completed: true
  reminders:
    - on time
    - 1 hour
  repeatFlag: weekly
```

### Better errors

- An unrecognised reminder, repeat rule or subtask fails with a message listing the accepted formats, before anything is sent to TickTick.
- TickTick answers an unknown project ID with a bare 500. Task services now add that the project ID is not one of your projects and point to `ticktick.get_projects`.

### Documentation

- Reworked README: new header, feature list, service tables with an example, known limitations, and support and credits sections.


## 2.3.0

Adds the project services that were on the README's to-do list. Requires Home Assistant 2026.10 or newer.

### New services

- `ticktick.get_project`: one project by ID
- `ticktick.get_detailed_project`: one project with its tasks, including the task IDs the task services need
- `ticktick.create_project`: `name` is required; `color`, `sortOrder`, `viewMode` and `kind` are optional
- `ticktick.update_project`: changes only the fields you pass
- `ticktick.delete_project`: deletes the project and all its tasks

Creating, updating or deleting a project reloads the integration, so the matching to-do list is added, renamed or removed right away. Deleting a project also removes its to-do list entity.

### Development

- The Docker image for `scripts/develop.sh` now includes a compiler and ffmpeg, so the throwaway Home Assistant no longer hangs on "Loading"
- 8 new tests for the project services (33 in total)


## 2.2.0

First release of this fork of [Hantick/ticktick-home-assistant](https://github.com/Hantick/ticktick-home-assistant), updated for current Home Assistant. Requires Home Assistant 2026.10 or newer.

### Fixes (from open upstream pull requests)

- Expired TickTick token now starts a re-authentication flow instead of failing with `KeyError: 'refresh_token'` (upstream #48)
- `complete_task` and `delete_task` services no longer fail on `returnAsJson` (upstream #37)
- All-day due dates work in both directions (upstream #50)
- Emptying a list no longer leaves the last item showing (upstream #47)
- To-do lists refresh right after a service changes a task (upstream #49)
- Checklist tasks use `desc` as their description (upstream #51)
- Brand icon and logo ship with the integration (upstream #52)

### Changes

- **Breaking:** services now fail with a Home Assistant error instead of returning `{"error": ...}`
- Services are registered once at startup rather than per config entry
- Internal clean-up for current Home Assistant APIs (`runtime_data`, relative imports)

### Development

- Test suite (25 tests), lint and CI
- Devcontainer, plus scripts to run the tests and a throwaway Home Assistant in Docker

