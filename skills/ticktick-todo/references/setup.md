# TickTick / Dida365 Setup

## Developer App

Create a developer app:

- China Dida365: `https://developer.dida365.com/manage`
- Global TickTick: `https://developer.ticktick.com/manage`

Use:

```text
OAuth redirect URL: http://127.0.0.1:8765/callback
Scopes: tasks:read tasks:write
```

## OAuth Regions

Use `--region dida` for China:

```text
auth: https://dida365.com/oauth/authorize
token: https://dida365.com/oauth/token
api: https://api.dida365.com/open/v1
```

Use `--region ticktick` for global:

```text
auth: https://ticktick.com/oauth/authorize
token: https://ticktick.com/oauth/token
api: https://api.ticktick.com/open/v1
```

## Reminder Format

The Open API accepts reminders such as:

```text
TRIGGER:PT0S
```

Use this together with a due date.
