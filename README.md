# ticktick-todo Codex Skill

Codex Skill for connecting Codex to TickTick / Dida365 todo lists.

Project URL:

https://github.com/dongximuye/ticktick-todo-codex-skill

## What Codex Can Do

- Install this Skill from GitHub
- Guide the user to create a TickTick/Dida365 developer app
- Store Client ID / Client Secret locally
- Start the local OAuth callback server
- Open the authorization URL
- Exchange the OAuth code for an access token
- Store tokens locally in `~/.codex_ticktick_todo_config.json`
- Create a dedicated todo project/list
- Create tasks with title, content, due date, and reminder
- Read projects/tasks back through the official Open API

The user still needs to do only the account-security steps:

- Log in to TickTick/Dida365 in the browser
- Click Allow on the OAuth authorization page

Secrets are stored only on the user's machine and are not committed to this repo.

## One-Prompt Install

Use this prompt in a new Codex thread:

```text
Use skill-installer to install the GitHub skill at dongximuye/ticktick-todo-codex-skill, path skills/ticktick-todo. After installation, restart/pick up the skill, then configure TickTick/Dida365 OAuth for me. Do every step you can; only pause for me to log in to TickTick/Dida365 and click Allow.
```

## Manual Install Command

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo dongximuye/ticktick-todo-codex-skill \
  --path skills/ticktick-todo
```

Windows users can ask Codex to run the equivalent local `skill-installer` command.

## Developer App Setup

Codex should guide the user to create an app at:

- China Dida365: https://developer.dida365.com/manage
- Global TickTick: https://developer.ticktick.com/manage

Use this redirect URL:

```text
http://127.0.0.1:8765/callback
```

Required OAuth scope:

```text
tasks:read tasks:write
```

Recommended app name:

```text
Codex Todo Assistant
```

After app creation, Codex should run:

```bash
python scripts/ticktick_connector.py configure-client --region dida
python scripts/ticktick_connector.py oauth-login --region dida --open-browser
python scripts/ticktick_connector.py api-status
python scripts/ticktick_connector.py ensure-project --name "CodexTest" --set-default
python scripts/ticktick_connector.py create-task --title "Codex API test" --content "Created by Codex." --read-back
```

For global TickTick, use `--region ticktick`.
