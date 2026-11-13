# Home Assistant TickTick Integration

![Static Badge](https://img.shields.io/badge/made%20with-fun-green?style=for-the-badge)‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎ ‎

Fork of [Hantick/ticktick-home-assistant](https://github.com/Hantick/ticktick-home-assistant), updated for current Home Assistant releases.

Integration implements [TickTick Open API](https://developer.ticktick.com/docs#/openapi) with support for [To-do list](https://www.home-assistant.io/integrations/todo/) entities and exposes it as services in Home Assistant, allowing you to manage your tasks and projects programmatically 😎

## Buy me a coffee or beer 🍻
<a href="https://paypal.me/hantick" target="_blank" rel="noopener noreferrer">
    <img src="https://www.paypalobjects.com/marketing/web/logos/paypal-mark-color.svg" alt="PayPal" height="40"></a>

## Installation

1. Navigate to [TickTick Developer](https://developer.ticktick.com/manage) and click `New App`
2. Name your app and set `OAuth redirect URL` to `https://my.home-assistant.io/redirect/oauth` or your instance url i.e `http://homeassistant.local:8123`
3. Add this repository as a custom repository in Settings → Marketplace (HACS on Home Assistant older than 2026.11) and download the TickTick integration
4. In Settings → Devices & services, use the dotted menu to create new application credentials (`/config/application_credentials`). Enter the OAuth client ID and secret from the TickTick app here.
5. Your TickTick Lists should now each turn up as a todo list in Home Assistant.

If you don’t want all of your lists to show up in the todo list app, you can disable selected lists in the entities list
(enter selection mode → Disable selected).

## Development

Everything runs in Docker, so no local Python is needed.

- **Tests and lint:** `bash scripts/test.sh` runs `ruff` and `pytest` in a container, the same checks as CI.
- **Devcontainer:** open the repository in VS Code and choose "Reopen in Container" (or use GitHub Codespaces). Tests then run with plain `pytest`.
- **Try it in Home Assistant:** inside the devcontainer, `bash scripts/develop.sh` starts a throwaway Home Assistant on http://localhost:8123 with the integration loaded. Its data lives in `./config`, which is not committed.

## Exposed Services

### Task Services

Get, Create, Update, Delete, Complete Task

### Project Services

Get (Create, Update, Delete are missing for now)

## Left to be done:

- Create/Update Task Service: `items` - The list of subtasks
- Create/Update Task Service: `reminders` - Can create some better builder for reminders
- Create/Update Task Service: `repeatFlag` - Can create some better builder for reminders
- Get Project By ID Service
- Get Project By ID With Data Service
- Create Project
- Update Project
- Delete Project
