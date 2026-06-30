---
name: ticktick-todo
description: Manage TickTick/Dida365 todos from Codex. Use when the user wants Codex to view todo projects, create tasks, add reminders, configure TickTick/Dida365 OAuth, inspect the local desktop TickTick database read-only, or turn chat notes into TickTick todo drafts.
---

# TickTick Todo

## Use The Script

Use the bundled script. Resolve the skill folder first, then run:

```bash
python scripts/ticktick_connector.py <command>
```

Do not print access tokens, refresh tokens, client secrets, cookies, passwords, or desktop database credential fields.

## Workflow

1. Run `api-status` to see whether OAuth is configured.
2. If not configured, help the user create a Dida365/TickTick developer app with redirect URL `http://127.0.0.1:8765/callback`.
3. Store client credentials with `configure-client`, then run `oauth-login --region dida` for China or `oauth-login --region ticktick` for global.
4. Use `api-projects`, `ensure-project`, and `create-task` for reliable task creation.
5. Use local SQLite commands (`status`, `projects`, `today`, `recent`, `find`) only for read-only desktop inspection.
6. Use `url-add --open` only as a fallback for simple task creation without official API credentials.

## Common Commands

```bash
python scripts/ticktick_connector.py api-status
python scripts/ticktick_connector.py configure-client --region dida
python scripts/ticktick_connector.py oauth-login --region dida --open-browser
python scripts/ticktick_connector.py api-projects
python scripts/ticktick_connector.py ensure-project --name "Codex测试" --set-default
python scripts/ticktick_connector.py create-task --title "测试标题" --content "测试内容"
python scripts/ticktick_connector.py create-task --title "带提醒" --due "2026-06-30T15:59:00+0000" --remind "TRIGGER:PT0S"
python scripts/ticktick_connector.py today
python scripts/ticktick_connector.py draft --text "待办内容"
```

## Safety Defaults

- Querying projects and creating clearly requested tasks is allowed.
- Completing, deleting, or modifying existing real tasks requires explicit confirmation.
- Never write directly to `TickTick.db`.
- Prefer creating or using a dedicated test/project list before writing real workflow tasks.

## Notes

- China Dida365 API base: `https://api.dida365.com/open/v1`
- Global TickTick API base: `https://api.ticktick.com/open/v1`
- OAuth scopes: `tasks:read tasks:write`
- Local config file: `~/.codex_ticktick_todo_config.json`

