---
name: ticktick-todo
description: Manage TickTick/Dida365 todos from Codex. Use when the user wants Codex to install or configure TickTick/Dida365 OAuth, view todo projects, create tasks, add due dates or reminders, inspect the local desktop TickTick database read-only, or turn chat notes into todo drafts.
---

# TickTick Todo

## Core Rule

Use the bundled script from this skill folder:

```bash
python scripts/ticktick_connector.py <command>
```

Never print access tokens, refresh tokens, client secrets, cookies, passwords, or desktop database credential fields.

## Full Setup Workflow

Do as much as possible yourself. Pause only when the user must log in to TickTick/Dida365 or click Allow on an OAuth page.

1. Run `api-status`.
2. If OAuth is missing, guide the user to create a developer app:
   - China Dida365: `https://developer.dida365.com/manage`
   - Global TickTick: `https://developer.ticktick.com/manage`
   - App name: `Codex Todo Assistant`
   - Redirect URL: `http://127.0.0.1:8765/callback`
   - Scope: `tasks:read tasks:write`
3. Store client credentials:
   - China: `python scripts/ticktick_connector.py configure-client --region dida`
   - Global: `python scripts/ticktick_connector.py configure-client --region ticktick`
4. Start OAuth:
   - China: `python scripts/ticktick_connector.py oauth-login --region dida --open-browser`
   - Global: `python scripts/ticktick_connector.py oauth-login --region ticktick --open-browser`
5. Ask the user to log in and click Allow if needed.
6. Verify:
   - `python scripts/ticktick_connector.py api-status`
   - `python scripts/ticktick_connector.py api-projects`
7. Create or reuse a dedicated project:
   - `python scripts/ticktick_connector.py ensure-project --name "CodexTest" --set-default`
8. Test task creation and readback:
   - `python scripts/ticktick_connector.py create-task --title "Codex API test" --content "Created by Codex." --read-back`

## Daily Use

Use official API commands for reliable task creation:

```bash
python scripts/ticktick_connector.py create-task --title "Task title" --content "Task note"
python scripts/ticktick_connector.py create-task --title "Reminder task" --due "2026-06-30T15:59:00+0000" --remind "TRIGGER:PT0S"
python scripts/ticktick_connector.py project-data
```

Use local desktop inspection only as read-only fallback:

```bash
python scripts/ticktick_connector.py status
python scripts/ticktick_connector.py today
python scripts/ticktick_connector.py recent --limit 5
```

Use URL Scheme only as fallback for simple tasks when OAuth is unavailable:

```bash
python scripts/ticktick_connector.py url-add --title "Task title" --open
```

## Safety Defaults

- Querying projects and creating clearly requested tasks is allowed.
- Completing, deleting, or modifying existing real tasks requires explicit confirmation.
- Never write directly to `TickTick.db`.
- Prefer a dedicated test/project list before writing real workflow tasks.

## Notes

- China Dida365 API base: `https://api.dida365.com/open/v1`
- Global TickTick API base: `https://api.ticktick.com/open/v1`
- OAuth scopes: `tasks:read tasks:write`
- Local private config file: `~/.codex_ticktick_todo_config.json`
