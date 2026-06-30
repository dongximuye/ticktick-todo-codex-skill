#!/usr/bin/env python3
"""Safe TickTick/Dida365 connector for Codex.

No third-party Python packages are required.
Secrets are stored in ~/.codex_ticktick_todo_config.json unless environment
variables are already set.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import getpass
import json
import os
import platform
import secrets
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

CONFIG_PATH = Path.home() / ".codex_ticktick_todo_config.json"
DEFAULT_SCOPE = "tasks:read tasks:write"
REGIONS = {
    "dida": {
        "api_base": "https://api.dida365.com/open/v1",
        "auth_url": "https://dida365.com/oauth/authorize",
        "token_url": "https://dida365.com/oauth/token",
    },
    "ticktick": {
        "api_base": "https://api.ticktick.com/open/v1",
        "auth_url": "https://ticktick.com/oauth/authorize",
        "token_url": "https://ticktick.com/oauth/token",
    },
}


def _json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def _load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid config JSON at {CONFIG_PATH}: {exc}") from exc


def _save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        pass


def _win_user_env(name: str) -> str | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except Exception:
        return None


def _env(name: str, default: str | None = None) -> str | None:
    config = _load_config()
    return os.environ.get(name) or _win_user_env(name) or config.get(name) or default


def _set_secret(name: str, value: str) -> None:
    config = _load_config()
    config[name] = value
    _save_config(config)


def _default_db() -> Path:
    override = _env("TICKTICK_DB")
    if override:
        return Path(override).expanduser()
    system = platform.system().lower()
    if system == "windows":
        return Path(os.environ.get("APPDATA", "")) / "Tick_Tick" / "TickTick.db"
    if system == "darwin":
        candidates = [
            Path.home() / "Library/Containers/com.TickTick.task.mac/Data/Library/Application Support/Tick_Tick/TickTick.db",
            Path.home() / "Library/Application Support/Tick_Tick/TickTick.db",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]
    return Path.home() / ".config/Tick_Tick/TickTick.db"


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise SystemExit(f"TickTick database not found: {db_path}")
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _table_names(con: sqlite3.Connection) -> list[str]:
    rows = con.execute("select name from sqlite_master where type='table' order by name").fetchall()
    return [row["name"] for row in rows]


def _load_projects(con: sqlite3.Connection) -> dict[str, str]:
    if "ProjectModel" not in _table_names(con):
        return {}
    rows = con.execute("select id, name from ProjectModel where closed = 0 or closed is null").fetchall()
    return {str(row["id"]): str(row["name"]) for row in rows}


def _parse_time(value: Any) -> dt.datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for candidate in (text, text.replace("Z", "+00:00"), text.replace(" ", "T")):
        try:
            parsed = dt.datetime.fromisoformat(candidate)
            return parsed.astimezone().replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(text[: len(fmt)], fmt)
        except ValueError:
            pass
    return None


def _task_is_today(row: sqlite3.Row, today: dt.date) -> bool:
    return any((_parse_time(row[key]) or dt.datetime.min).date() == today for key in ("startDate", "dueDate", "remindTime"))


def _region_config(region: str | None = None) -> dict[str, str]:
    chosen = region or _env("TICKTICK_REGION", "dida") or "dida"
    if chosen not in REGIONS:
        raise SystemExit(f"Unknown region {chosen!r}; use dida or ticktick")
    return REGIONS[chosen]


def _api_base() -> str:
    return _env("TICKTICK_API_BASE") or _env("DIDA_API_BASE") or _region_config()["api_base"]


def _api_headers() -> dict[str, str]:
    token = _env("TICKTICK_ACCESS_TOKEN") or _env("DIDA_ACCESS_TOKEN")
    if not token:
        raise SystemExit("Missing access token. Run configure-client and oauth-login first.")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(_api_base().rstrip("/") + path, data=body, method=method, headers=_api_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = res.read().decode("utf-8")
            return json.loads(data) if data else {"ok": True}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"API error {exc.code}: {detail[:500]}")


def cmd_configure_client(args: argparse.Namespace) -> None:
    region = _region_config(args.region)
    client_id = args.client_id or input("Client ID: ").strip()
    client_secret = args.client_secret or getpass.getpass("Client Secret: ").strip()
    if not client_id or not client_secret:
        raise SystemExit("Client ID and Client Secret are required")
    _set_secret("TICKTICK_CLIENT_ID", client_id)
    _set_secret("DIDA_CLIENT_ID", client_id)
    _set_secret("TICKTICK_CLIENT_SECRET", client_secret)
    _set_secret("DIDA_CLIENT_SECRET", client_secret)
    _set_secret("TICKTICK_REGION", args.region)
    _set_secret("TICKTICK_API_BASE", region["api_base"])
    _set_secret("DIDA_API_BASE", region["api_base"])
    _json({"saved": True, "config_path": str(CONFIG_PATH), "client_id": "redacted", "client_secret": "redacted", "api_base": region["api_base"]})


def cmd_oauth_url(args: argparse.Namespace) -> None:
    region = _region_config(args.region)
    client_id = _env("TICKTICK_CLIENT_ID") or _env("DIDA_CLIENT_ID")
    if not client_id:
        raise SystemExit("Missing client id. Run configure-client first.")
    state = args.state or secrets.token_urlsafe(16)
    params = {"client_id": client_id, "scope": args.scope, "state": state, "redirect_uri": args.redirect_uri, "response_type": "code"}
    _json({"auth_url": region["auth_url"] + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote), "state": state})


def _exchange_code(region: dict[str, str], code: str, scope: str, redirect_uri: str) -> dict[str, Any]:
    client_id = _env("TICKTICK_CLIENT_ID") or _env("DIDA_CLIENT_ID")
    client_secret = _env("TICKTICK_CLIENT_SECRET") or _env("DIDA_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("Missing client credentials. Run configure-client first.")
    body = urllib.parse.urlencode({"code": code, "grant_type": "authorization_code", "scope": scope, "redirect_uri": redirect_uri}).encode("utf-8")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(region["token_url"], data=body, method="POST", headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OAuth token exchange failed {exc.code}: {detail[:500]}")


def _save_token(data: dict[str, Any], api_base: str) -> None:
    access = data.get("access_token")
    if not access:
        raise SystemExit("Token response did not include access_token")
    _set_secret("TICKTICK_ACCESS_TOKEN", access)
    _set_secret("DIDA_ACCESS_TOKEN", access)
    _set_secret("TICKTICK_API_BASE", api_base)
    _set_secret("DIDA_API_BASE", api_base)
    if data.get("refresh_token"):
        _set_secret("TICKTICK_REFRESH_TOKEN", data["refresh_token"])
        _set_secret("DIDA_REFRESH_TOKEN", data["refresh_token"])


def cmd_oauth_login(args: argparse.Namespace) -> None:
    region = _region_config(args.region)
    client_id = _env("TICKTICK_CLIENT_ID") or _env("DIDA_CLIENT_ID")
    if not client_id:
        raise SystemExit("Missing client id. Run configure-client first.")
    state = secrets.token_urlsafe(16)
    params = {"client_id": client_id, "scope": args.scope, "state": state, "redirect_uri": args.redirect_uri, "response_type": "code"}
    auth_url = region["auth_url"] + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *handler_args: Any) -> None:
            return

        def do_GET(self) -> None:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code = query.get("code", [""])[0]
            got_state = query.get("state", [""])[0]
            ok = bool(code and got_state == state)
            self.send_response(200 if ok else 400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(("Authorization succeeded. Return to Codex." if ok else "Authorization failed.").encode("utf-8"))
            self.server.result = {"code": code} if ok else {"error": "missing_code_or_state_mismatch"}  # type: ignore[attr-defined]

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    server.timeout = args.timeout
    _json({"auth_url": auth_url, "listening": args.redirect_uri, "token": "will_not_be_printed"})
    if args.open_browser:
        webbrowser.open(auth_url)
    server.handle_request()
    result = getattr(server, "result", None)
    if not result or result.get("error"):
        raise SystemExit(f"OAuth callback failed: {result}")
    data = _exchange_code(region, result["code"], args.scope, args.redirect_uri)
    _save_token(data, region["api_base"])
    _json({"oauth_complete": True, "access_token": "redacted", "refresh_token": "redacted" if data.get("refresh_token") else None, "expires_in": data.get("expires_in"), "scope": data.get("scope"), "api_base": region["api_base"]})


def cmd_api_status(args: argparse.Namespace) -> None:
    _json({"api_base": _api_base(), "token_present": bool(_env("TICKTICK_ACCESS_TOKEN") or _env("DIDA_ACCESS_TOKEN")), "client_id_present": bool(_env("TICKTICK_CLIENT_ID") or _env("DIDA_CLIENT_ID")), "client_secret_present": bool(_env("TICKTICK_CLIENT_SECRET") or _env("DIDA_CLIENT_SECRET")), "default_project_id_present": bool(_env("TICKTICK_DEFAULT_PROJECT_ID") or _env("DIDA_DEFAULT_PROJECT_ID")), "config_path": str(CONFIG_PATH)})


def cmd_api_projects(args: argparse.Namespace) -> None:
    _json(_request("GET", "/project"))


def cmd_ensure_project(args: argparse.Namespace) -> None:
    projects = _request("GET", "/project")
    for project in projects:
        if project.get("name") == args.name:
            if args.set_default:
                _set_secret("TICKTICK_DEFAULT_PROJECT_ID", project["id"])
                _set_secret("DIDA_DEFAULT_PROJECT_ID", project["id"])
            _json({"created": False, "project": project, "default_project_saved": bool(args.set_default)})
            return
    payload = {"name": args.name, "color": args.color, "viewMode": args.view_mode, "kind": "TASK"}
    created = _request("POST", "/project", payload)
    if args.set_default and created.get("id"):
        _set_secret("TICKTICK_DEFAULT_PROJECT_ID", created["id"])
        _set_secret("DIDA_DEFAULT_PROJECT_ID", created["id"])
    _json({"created": True, "project": created, "default_project_saved": bool(args.set_default and created.get("id"))})


def cmd_project_data(args: argparse.Namespace) -> None:
    project_id = args.project_id or _env("TICKTICK_DEFAULT_PROJECT_ID") or _env("DIDA_DEFAULT_PROJECT_ID")
    if not project_id:
        raise SystemExit("Missing project id. Pass --project-id or run ensure-project --set-default.")
    _json(_request("GET", f"/project/{urllib.parse.quote(project_id)}/data"))


def cmd_create_task(args: argparse.Namespace) -> None:
    project_id = args.project_id or _env("TICKTICK_DEFAULT_PROJECT_ID") or _env("DIDA_DEFAULT_PROJECT_ID")
    if not project_id:
        raise SystemExit("Missing project id. Pass --project-id or run ensure-project --set-default.")
    payload: dict[str, Any] = {"title": args.title, "projectId": project_id}
    if args.content:
        payload["content"] = args.content
    if args.due:
        payload["dueDate"] = args.due
    if args.remind:
        payload["reminders"] = [args.remind]
    created = _request("POST", "/task", payload)
    read_back = _request("GET", f"/project/{urllib.parse.quote(project_id)}/data") if args.read_back else None
    _json({"created": created, "read_back": read_back})


def cmd_status(args: argparse.Namespace) -> None:
    db_path = Path(args.db).expanduser()
    con = _connect_readonly(db_path)
    tables = set(_table_names(con))
    important = ["TaskModel", "TaskReminderModel", "ProjectModel", "CalendarEventModel", "UserModel"]
    _json({"mode": "local_sqlite_readonly", "db_path": str(db_path), "detected_tables": [name for name in important if name in tables], "write_policy": "local database write is disabled"})


def cmd_projects(args: argparse.Namespace) -> None:
    con = _connect_readonly(Path(args.db).expanduser())
    _json([{"id": pid, "name": name} for pid, name in _load_projects(con).items()])


def cmd_today(args: argparse.Namespace) -> None:
    con = _connect_readonly(Path(args.db).expanduser())
    projects = _load_projects(con)
    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    rows = con.execute("select id, projectId, title, priority, status, startDate, dueDate, remindTime, deleted, content from TaskModel where deleted = 0 or deleted is null").fetchall()
    tasks = []
    for row in rows:
        if _task_is_today(row, today):
            item = {"id": row["id"], "title": row["title"], "project": projects.get(str(row["projectId"]), ""), "priority": row["priority"], "status": row["status"], "start": row["startDate"], "due": row["dueDate"], "remind": row["remindTime"]}
            if args.include_content:
                item["content"] = row["content"]
            tasks.append(item)
    _json({"date": str(today), "source": "local_sqlite_readonly", "tasks": tasks})


def cmd_recent(args: argparse.Namespace) -> None:
    con = _connect_readonly(Path(args.db).expanduser())
    projects = _load_projects(con)
    rows = con.execute("select id, projectId, title, priority, status, startDate, dueDate, remindTime, deleted, createdTime, modifiedTime from TaskModel order by _Id desc limit ?", (args.limit,)).fetchall()
    _json([{"id": row["id"], "title": row["title"], "project": projects.get(str(row["projectId"]), ""), "status": row["status"], "due": row["dueDate"], "remind": row["remindTime"], "deleted": row["deleted"], "created": row["createdTime"], "modified": row["modifiedTime"]} for row in rows])


def cmd_find(args: argparse.Namespace) -> None:
    con = _connect_readonly(Path(args.db).expanduser())
    projects = _load_projects(con)
    rows = con.execute("select id, projectId, title, priority, status, startDate, dueDate, remindTime, deleted, createdTime, modifiedTime from TaskModel where title like ? order by modifiedTime desc limit ?", (f"%{args.title}%", args.limit)).fetchall()
    _json([{"id": row["id"], "title": row["title"], "project": projects.get(str(row["projectId"]), ""), "status": row["status"], "due": row["dueDate"], "remind": row["remindTime"], "deleted": row["deleted"], "created": row["createdTime"], "modified": row["modifiedTime"]} for row in rows])


def cmd_draft(args: argparse.Namespace) -> None:
    text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else args.text
    if not text:
        raise SystemExit("Missing draft text. Pass --text or --text-file.")
    _json({"title": args.title or text.strip().splitlines()[0][:80], "content": text, "project": args.project or "CodexTest", "due": args.due, "remind": args.remind, "write_status": "draft_only_not_sent_to_ticktick"})


def cmd_url_add(args: argparse.Namespace) -> None:
    params = {"title": args.title}
    for key, value in {"content": args.content, "list": args.list, "startDate": args.start, "dueDate": args.due, "reminder": args.remind, "priority": args.priority}.items():
        if value:
            params[key] = value
    url = "ticktick://x-callback-url/v1/add_task?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    if args.open:
        if os.name == "nt":
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            webbrowser.open(url)
    _json({"mode": "desktop_url_scheme", "url": url, "opened": bool(args.open)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe Codex connector for TickTick/Dida365")
    parser.add_argument("--db", default=str(_default_db()), help="TickTick SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("configure-client", help="Save OAuth client id/secret locally")
    p.add_argument("--region", choices=sorted(REGIONS), default="dida")
    p.add_argument("--client-id")
    p.add_argument("--client-secret")
    p.set_defaults(func=cmd_configure_client)

    p = sub.add_parser("oauth-url", help="Build authorization URL")
    p.add_argument("--region", choices=sorted(REGIONS), default=None)
    p.add_argument("--redirect-uri", default="http://127.0.0.1:8765/callback")
    p.add_argument("--scope", default=DEFAULT_SCOPE)
    p.add_argument("--state")
    p.set_defaults(func=cmd_oauth_url)

    p = sub.add_parser("oauth-login", help="Run local OAuth callback and save token")
    p.add_argument("--region", choices=sorted(REGIONS), default=None)
    p.add_argument("--redirect-uri", default="http://127.0.0.1:8765/callback")
    p.add_argument("--scope", default=DEFAULT_SCOPE)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--timeout", type=int, default=240)
    p.add_argument("--open-browser", action="store_true")
    p.set_defaults(func=cmd_oauth_login)

    sub.add_parser("api-status").set_defaults(func=cmd_api_status)
    sub.add_parser("api-projects").set_defaults(func=cmd_api_projects)

    p = sub.add_parser("ensure-project")
    p.add_argument("--name", default="CodexTest")
    p.add_argument("--color", default="#4C9AFF")
    p.add_argument("--view-mode", default="list")
    p.add_argument("--set-default", action="store_true")
    p.set_defaults(func=cmd_ensure_project)

    p = sub.add_parser("project-data")
    p.add_argument("--project-id")
    p.set_defaults(func=cmd_project_data)

    p = sub.add_parser("create-task")
    p.add_argument("--project-id")
    p.add_argument("--title", required=True)
    p.add_argument("--content")
    p.add_argument("--due")
    p.add_argument("--remind")
    p.add_argument("--read-back", action="store_true", default=True)
    p.set_defaults(func=cmd_create_task)

    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("projects").set_defaults(func=cmd_projects)

    p = sub.add_parser("today")
    p.add_argument("--date")
    p.add_argument("--include-content", action="store_true")
    p.set_defaults(func=cmd_today)

    p = sub.add_parser("recent")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_recent)

    p = sub.add_parser("find")
    p.add_argument("--title", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("draft")
    p.add_argument("--text")
    p.add_argument("--text-file")
    p.add_argument("--title")
    p.add_argument("--project")
    p.add_argument("--due")
    p.add_argument("--remind")
    p.set_defaults(func=cmd_draft)

    p = sub.add_parser("url-add")
    p.add_argument("--title", required=True)
    p.add_argument("--content")
    p.add_argument("--list")
    p.add_argument("--start")
    p.add_argument("--due")
    p.add_argument("--remind")
    p.add_argument("--priority")
    p.add_argument("--open", action="store_true")
    p.set_defaults(func=cmd_url_add)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
