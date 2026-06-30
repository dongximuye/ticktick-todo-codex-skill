# ticktick-todo Codex Skill

Codex Skill for connecting Codex to TickTick / Dida365 todo lists.

It supports:

- OAuth setup for Dida365 China or TickTick global Open API
- project listing and project creation
- creating tasks with title, content, due date, and reminders
- safe local read-only inspection of the desktop SQLite database when available
- desktop URL Scheme fallback for creating simple tasks

Secrets are stored only on the user's machine, in `~/.codex_ticktick_todo_config.json`, and are not committed to this repo.

## Install

Ask Codex:

```text
安装 GitHub 上 dongximuye/ticktick-todo-codex-skill 仓库里的 skills/ticktick-todo 这个 Skill，然后重启 Codex。
```

Or manually:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo dongximuye/ticktick-todo-codex-skill \
  --path skills/ticktick-todo
```

## First setup

Create an app at:

- China Dida365: https://developer.dida365.com/manage
- Global TickTick: https://developer.ticktick.com/manage

Use this redirect URL:

```text
http://127.0.0.1:8765/callback
```

Then ask Codex:

```text
使用 ticktick-todo Skill，帮我配置滴答清单国内版 OAuth，并创建一个 Codex测试 项目。
```

