from __future__ import annotations

import argparse
import errno
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def default_codex_home() -> Path:
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser()
    return Path.home() / ".codex"


@dataclass
class Paths:
    codex_home: Path
    config_path: Path
    auth_path: Path
    db_path: Path
    backup_dir: Path


REQUIRED_THREAD_COLUMNS = {
    "id",
    "rollout_path",
    "updated_at",
    "model_provider",
    "title",
    "archived",
    "model",
}

SESSION_HISTORY_DIRS = ("sessions", "archived_sessions")


def resolve_paths(codex_home: str | None) -> Paths:
    home = Path(codex_home).expanduser() if codex_home else default_codex_home()
    return Paths(
        codex_home=home,
        config_path=home / "config.toml",
        auth_path=home / "auth.json",
        db_path=home / "state_5.sqlite",
        backup_dir=home / "history_sync_backups",
    )


def detect_platform() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    return system or "unknown"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_current_provider(config_text: str) -> str | None:
    match = re.search(r'(?m)^\s*model_provider\s*=\s*"([^"]+)"', config_text)
    return match.group(1) if match else None


def parse_current_model(config_text: str) -> str | None:
    match = re.search(r'(?m)^\s*model\s*=\s*"([^"]+)"', config_text)
    return match.group(1) if match else None


def read_auth_mode(paths: Paths) -> str | None:
    if not paths.auth_path.exists():
        return None
    try:
        payload = json.loads(read_text(paths.auth_path))
    except (OSError, json.JSONDecodeError):
        return None
    auth_mode = payload.get("auth_mode")
    return auth_mode if isinstance(auth_mode, str) and auth_mode.strip() else None


def infer_provider_from_auth(auth_mode: str | None) -> tuple[str | None, str | None]:
    if not auth_mode:
        return None, None

    normalized = auth_mode.strip().lower()
    if normalized in {"chatgpt", "openai", "openai_api_key", "api_key"}:
        return "openai", f"auth_mode:{normalized}"

    return None, None


def connect_db(path: Path, readonly: bool = False, timeout: float = 30) -> sqlite3.Connection:
    if readonly:
        uri_path = path.resolve().as_posix()
        return sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True, timeout=timeout)
    conn = sqlite3.connect(str(path), timeout=timeout)
    conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)}")
    return conn


def ensure_environment(paths: Paths) -> None:
    if not paths.config_path.exists():
        raise RuntimeError(f"Missing config file: {paths.config_path}")
    if not paths.db_path.exists():
        raise RuntimeError(f"Missing database file: {paths.db_path}")


def validate_threads_schema(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("PRAGMA table_info(threads)").fetchall()
    columns = {str(row[1]) for row in rows}
    missing = sorted(REQUIRED_THREAD_COLUMNS - columns)
    if missing:
        raise RuntimeError(f"Database table 'threads' is missing required columns: {', '.join(missing)}")
    return sorted(columns)


def check_database_writable(paths: Paths) -> None:
    with connect_db(paths.db_path, readonly=False, timeout=1) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.rollback()


def check_backup_dir_writable(paths: Paths) -> None:
    paths.backup_dir.mkdir(parents=True, exist_ok=True)
    probe = paths.backup_dir / f".preflight-{os.getpid()}.tmp"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)


def check_rewrite_target(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Session history file does not exist: {path}")
    if not path.is_file():
        raise RuntimeError(f"Session history path is not a file: {path}")
    with path.open("r+", encoding="utf-8", errors="replace"):
        pass
    probe = path.parent / f".{path.name}.preflight-{os.getpid()}.tmp"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)


def detect_codex_home(codex_home: str | None = None) -> dict[str, object]:
    paths = resolve_paths(codex_home)
    return {
        "platform": detect_platform(),
        "codex_home": str(paths.codex_home),
        "config_path": str(paths.config_path),
        "auth_path": str(paths.auth_path),
        "db_path": str(paths.db_path),
        "backup_dir": str(paths.backup_dir),
        "config_exists": paths.config_path.exists(),
        "auth_exists": paths.auth_path.exists(),
        "db_exists": paths.db_path.exists(),
    }


def query_provider_counts(conn: sqlite3.Connection) -> OrderedDict[str, int]:
    counts = OrderedDict()
    for provider, count in conn.execute(
        """
        SELECT model_provider, COUNT(*)
        FROM threads
        GROUP BY model_provider
        ORDER BY COUNT(*) DESC, model_provider ASC
        """
    ):
        counts[provider or "(empty)"] = count
    return counts


def query_threads(conn: sqlite3.Connection, limit: int | None = None) -> list[dict[str, object]]:
    rows = []
    sql = "SELECT id, rollout_path, title, model_provider, archived FROM threads ORDER BY updated_at DESC"
    if limit is not None:
        sql += f" LIMIT {limit}"
    for row in conn.execute(sql):
        rows.append(
            {
                "id": row[0],
                "rollout_path": row[1],
                "title": row[2],
                "model_provider": row[3],
                "archived": row[4],
            }
        )
    return rows


def iter_session_meta_prefix(path: Path, max_lines: int | None = None) -> list[tuple[int, str, dict[str, object]]]:
    entries = []
    if not path.exists():
        return entries

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_index, line in enumerate(handle):
                if max_lines is not None and line_index >= max_lines:
                    break
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if payload.get("type") == "session_meta" and isinstance(payload.get("payload"), dict):
                    entries.append((line_index, line, payload))
    except OSError:
        return []

    return entries


def canonical_path_key(path_value: str | Path) -> str:
    try:
        path = Path(path_value).expanduser()
        return os.path.normcase(os.path.abspath(str(path)))
    except Exception:
        return os.path.normcase(str(path_value))


def session_file_candidates(paths: Paths) -> list[Path]:
    candidates: list[Path] = []
    for dirname in SESSION_HISTORY_DIRS:
        root = paths.codex_home / dirname
        if not root.exists():
            continue
        try:
            candidates.extend(item for item in root.rglob("*.jsonl") if item.is_file())
        except OSError:
            continue
    return sorted(candidates)


def parse_timestamp(value: object) -> tuple[int | None, int | None]:
    if isinstance(value, (int, float)):
        raw = float(value)
        if raw > 10_000_000_000:
            millis = int(raw)
            return millis // 1000, millis
        seconds = int(raw)
        return seconds, seconds * 1000

    if isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            normalized = text.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            seconds = int(parsed.timestamp())
            return seconds, seconds * 1000
        except ValueError:
            pass

    return None, None


def extract_text_from_content(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("input_text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part.strip() for part in parts if part and part.strip()).strip()
    return ""


def extract_user_message(record: dict[str, object]) -> str | None:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None

    item = payload.get("item") if record.get("type") == "response_item" else payload
    if not isinstance(item, dict):
        return None
    if item.get("type") != "message" or item.get("role") != "user":
        return None

    text = extract_text_from_content(item.get("content"))
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("<environment_context>") or stripped.startswith("<permissions instructions>"):
        return None
    return stripped


def short_text(value: str, limit: int = 160) -> str:
    collapsed = re.sub(r"\s+", " ", value).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def infer_session_id_from_filename(path: Path) -> str | None:
    match = re.search(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        path.stem,
    )
    return match.group(1) if match else None


def scan_session_file(path: Path) -> dict[str, object] | None:
    metas: list[dict[str, object]] = []
    first_user_message: str | None = None
    first_second: int | None = None
    first_millis: int | None = None
    last_second: int | None = None
    last_millis: int | None = None
    malformed_lines = 0
    line_count = 0

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line_count += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    malformed_lines += 1
                    continue
                if not isinstance(record, dict):
                    continue

                timestamp_value = record.get("timestamp")
                second, millis = parse_timestamp(timestamp_value)
                if second is not None:
                    if first_second is None or second < first_second:
                        first_second = second
                        first_millis = millis
                    if last_second is None or second > last_second:
                        last_second = second
                        last_millis = millis

                if record.get("type") == "session_meta" and isinstance(record.get("payload"), dict):
                    meta = record["payload"]
                    metas.append(meta)
                    meta_second, meta_millis = parse_timestamp(meta.get("timestamp"))
                    if meta_second is not None:
                        if first_second is None or meta_second < first_second:
                            first_second = meta_second
                            first_millis = meta_millis
                        if last_second is None or meta_second > last_second:
                            last_second = meta_second
                            last_millis = meta_millis

                if first_user_message is None:
                    first_user_message = extract_user_message(record)
    except OSError:
        return None

    if not metas and line_count == 0:
        return None

    stat = path.stat()
    fallback_second = int(stat.st_mtime)
    fallback_millis = int(stat.st_mtime * 1000)
    first_meta = metas[0] if metas else {}
    last_meta = metas[-1] if metas else first_meta
    session_id = first_meta.get("id") if isinstance(first_meta.get("id"), str) else infer_session_id_from_filename(path)
    if not session_id:
        return None

    title = short_text(first_user_message, 80) if first_user_message else "Recovered session"
    preview = short_text(first_user_message or title, 240)
    created_at = first_second if first_second is not None else fallback_second
    updated_at = last_second if last_second is not None else fallback_second
    created_at_ms = first_millis if first_millis is not None else fallback_millis
    updated_at_ms = last_millis if last_millis is not None else fallback_millis

    return {
        "id": session_id,
        "rollout_path": path.as_posix(),
        "created_at": created_at,
        "updated_at": updated_at,
        "created_at_ms": created_at_ms,
        "updated_at_ms": updated_at_ms,
        "source": first_meta.get("source") or "local",
        "thread_source": first_meta.get("thread_source"),
        "model_provider": last_meta.get("model_provider"),
        "model": last_meta.get("model"),
        "cwd": first_meta.get("cwd") or "",
        "title": title,
        "preview": preview,
        "first_user_message": short_text(first_user_message or title, 400),
        "has_user_event": 1 if first_user_message else 0,
        "sandbox_policy": first_meta.get("sandbox_policy") or "workspace-write",
        "approval_mode": first_meta.get("approval_mode") or first_meta.get("approval_policy") or "on-request",
        "cli_version": first_meta.get("cli_version") or "",
        "archived": 1 if "archived_sessions" in path.parts else 0,
        "malformed_lines": malformed_lines,
        "session_meta_count": len(metas),
    }


def scan_session_history(paths: Paths) -> dict[str, object]:
    files = session_file_candidates(paths)
    sessions: list[dict[str, object]] = []
    unreadable_files: list[str] = []
    malformed_files: list[dict[str, object]] = []

    for path in files:
        info = scan_session_file(path)
        if info is None:
            unreadable_files.append(str(path))
            continue
        sessions.append(info)
        if info.get("malformed_lines"):
            malformed_files.append({"path": str(path), "malformed_lines": info["malformed_lines"]})

    return {
        "files_found": len(files),
        "sessions": sessions,
        "unreadable_files": unreadable_files,
        "malformed_files": malformed_files,
    }


def query_session_meta_counts(threads: list[dict[str, object]], current_provider: str) -> dict[str, object]:
    provider_counts: OrderedDict[str, int] = OrderedDict()
    mismatched_threads = 0
    mismatched_files = 0
    missing_files = 0
    checked_files = 0
    seen_paths: set[Path] = set()

    for thread in threads:
        rollout_path = thread.get("rollout_path")
        if not isinstance(rollout_path, str) or not rollout_path:
            continue
        path = Path(rollout_path)
        if path in seen_paths:
            continue
        seen_paths.add(path)

        if not path.exists():
            missing_files += 1
            continue

        checked_files += 1
        metas = iter_session_meta_prefix(path)
        file_mismatched = False
        for _, _, payload in metas:
            inner = payload.get("payload")
            if not isinstance(inner, dict):
                continue
            provider = inner.get("model_provider")
            key = provider if isinstance(provider, str) and provider else "(empty)"
            provider_counts[key] = provider_counts.get(key, 0) + 1
            if provider != current_provider:
                mismatched_threads += 1
                file_mismatched = True
        if file_mismatched:
            mismatched_files += 1

    return {
        "checked_files": checked_files,
        "missing_files": missing_files,
        "mismatched_session_meta": mismatched_threads,
        "mismatched_session_files": mismatched_files,
        "session_meta_provider_counts": [
            {"provider": key, "count": value} for key, value in provider_counts.items()
        ],
    }

def infer_provider_from_threads(conn: sqlite3.Connection, current_model: str | None) -> tuple[str | None, str | None]:
    if current_model:
        row = conn.execute(
            """
            SELECT model_provider
            FROM threads
            WHERE model = ? AND model_provider <> ''
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (current_model,),
        ).fetchone()
        if row and row[0]:
            return row[0], "latest_thread_for_model"

    row = conn.execute(
        """
        SELECT model_provider
        FROM threads
        WHERE model_provider <> ''
        ORDER BY updated_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row and row[0]:
        return row[0], "latest_thread"

    return None, None


def list_backups(paths: Paths, limit: int = 20) -> list[dict[str, str]]:
    if not paths.backup_dir.exists():
        return []
    files = sorted(
        paths.backup_dir.glob("state_5.sqlite.*.bak"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    output = []
    for item in files[:limit]:
        sidecar = item.with_name(f"{item.name}.session-meta.json")
        output.append(
            {
                "name": item.name,
                "path": str(item),
                "size_bytes": item.stat().st_size,
                "modified_at": datetime.fromtimestamp(item.stat().st_mtime).isoformat(timespec="seconds"),
                "session_meta_backup_path": str(sidecar) if sidecar.exists() else None,
            }
        )
    return output


def inspect_backup(paths: Paths, backup_path: str) -> dict[str, object]:
    backup = resolve_backup(paths, backup_path)
    backup_dir = paths.backup_dir.resolve()
    resolved = backup.resolve()
    if backup_dir not in resolved.parents:
        raise RuntimeError(f"Refusing to read a file outside the backup directory: {backup}")
    sidecar = backup.with_name(f"{backup.name}.session-meta.json")
    with connect_db(backup, readonly=True) as conn:
        counts = query_provider_counts(conn)
        total_threads = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        rows = []
        for row in conn.execute(
            """
            SELECT id, title, model_provider, model, archived, updated_at
            FROM threads
            ORDER BY updated_at DESC
            LIMIT 200
            """
        ):
            rows.append(
                {
                    "id": row[0],
                    "title": row[1],
                    "model_provider": row[2],
                    "model": row[3],
                    "archived": row[4],
                    "updated_at": row[5],
                }
            )

    session_files = 0
    session_meta_lines = 0
    if sidecar.exists():
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        files = payload.get("files", [])
        if isinstance(files, list):
            session_files = len(files)
            for file_entry in files:
                lines = file_entry.get("lines", []) if isinstance(file_entry, dict) else []
                if isinstance(lines, list):
                    session_meta_lines += len(lines)

    return {
        "name": backup.name,
        "path": str(backup),
        "size_bytes": backup.stat().st_size,
        "modified_at": datetime.fromtimestamp(backup.stat().st_mtime).isoformat(timespec="seconds"),
        "total_threads": total_threads,
        "provider_counts": [{"provider": key, "count": value} for key, value in counts.items()],
        "threads": rows,
        "session_meta_backup_path": str(sidecar) if sidecar.exists() else None,
        "session_meta_files": session_files,
        "session_meta_lines": session_meta_lines,
    }


def delete_backup(paths: Paths, backup_path: str) -> dict[str, object]:
    backup = resolve_backup(paths, backup_path)
    backup_dir = paths.backup_dir.resolve()
    resolved = backup.resolve()
    if backup_dir not in resolved.parents:
        raise RuntimeError(f"Refusing to delete a file outside the backup directory: {backup}")

    deleted = []
    sidecar = backup.with_name(f"{backup.name}.session-meta.json")
    backup.unlink()
    deleted.append(str(backup))
    if sidecar.exists():
        sidecar.unlink()
        deleted.append(str(sidecar))
    return {"action": "delete-backup", "deleted": deleted, "backups": list_backups(paths)}


def _is_helper_process(name: str) -> bool:
    return name.lower() == "node_repl"


def manual_close_commands(processes: list[dict[str, object]], system: str) -> list[str]:
    pids = [str(item.get("pid")) for item in processes if item.get("pid")]
    if not pids:
        return []

    if system == "windows":
        pid_args = " ".join(f"/PID {pid}" for pid in pids)
        return [
            f"taskkill {pid_args} /T /F",
            "Get-Process Codex,codex,node_repl -ErrorAction SilentlyContinue | Stop-Process -Force",
        ]
    if system == "macos":
        return [
            f"kill {' '.join(pids)}",
            f"sudo kill -9 {' '.join(pids)}",
            "pkill -f 'Codex|codex|node_repl'",
        ]
    # linux and other unix-like systems
    return [
        f"kill {' '.join(pids)}",
        f"sudo kill -9 {' '.join(pids)}",
        "pkill -f 'codex|node_repl'",
    ]


def detect_codex_processes() -> dict[str, object]:
    system = detect_platform()
    processes: list[dict[str, object]] = []

    if system == "windows":
        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-Process | Where-Object { "
                "$_.ProcessName -match '^(Codex|codex)$' -or "
                "($_.Path -and $_.Path -match 'OpenAI\\\\Codex') "
                "} | Select-Object Id,ProcessName,Path | ConvertTo-Json -Compress"
            ),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                payload = []
            if isinstance(payload, dict):
                payload = [payload]
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        proc_name = str(item.get("ProcessName") or "").lower()
                        processes.append(
                            {
                                "pid": item.get("Id"),
                                "name": item.get("ProcessName"),
                                "path": item.get("Path"),
                                "kind": "helper" if _is_helper_process(proc_name) else "codex",
                            }
                        )
    elif system == "macos":
        result = subprocess.run(["ps", "-axo", "pid=,comm="], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                pid, _, command = stripped.partition(" ")
                name = Path(command.strip()).name
                if name.lower() == "codex" or "OpenAI Codex" in command or "/Codex.app/" in command:
                    processes.append(
                        {
                            "pid": int(pid),
                            "name": name,
                            "path": command.strip(),
                            "kind": "helper" if _is_helper_process(name) else "codex",
                        }
                    )
    else:
        # linux and other unix-like systems
        try:
            result = subprocess.run(["ps", "-axo", "pid=,comm="], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    pid, _, command = stripped.partition(" ")
                    name = Path(command.strip()).name
                    if name.lower() == "codex" or "codex" in command.lower():
                        processes.append(
                            {
                                "pid": int(pid),
                                "name": name,
                                "path": command.strip(),
                                "kind": "helper" if name.lower() == "node_repl" else "codex",
                            }
                        )
        except Exception:
            pass

    return {
        "platform": system,
        "running": len(processes) > 0,
        "processes": processes,
        "manual_commands": manual_close_commands(processes, system),
    }


def close_codex_processes() -> dict[str, object]:
    before = detect_codex_processes()
    system = before["platform"]
    closed: list[dict[str, object]] = []
    failed: list[dict[str, object]] = []

    for process in before["processes"]:
        pid = process.get("pid")
        if not pid or int(pid) == os.getpid():
            continue
        try:
            if system == "windows":
                result = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            else:
                # macOS and Linux both use kill
                result = subprocess.run(
                    ["kill", str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            if result.returncode == 0:
                closed.append(process)
            else:
                failed.append({**process, "error": (result.stderr or result.stdout).strip()})
        except Exception as exc:
            failed.append({**process, "error": str(exc)})

    after = detect_codex_processes()
    return {
        "action": "close-processes",
        "platform": system,
        "closed": closed,
        "failed": failed,
        "running": after["running"],
        "processes": after["processes"],
        "manual_commands": after["manual_commands"] or manual_close_commands(failed, system),
    }


def ensure_codex_not_running() -> None:
    state = detect_codex_processes()
    if state["running"]:
        names = ", ".join(f"{p.get('name')}({p.get('pid')})" for p in state["processes"])
        raise RuntimeError(f"Codex is still running. Close Codex and check again before syncing. Processes: {names}")


def get_status(paths: Paths) -> dict[str, object]:
    ensure_environment(paths)
    config_text = read_text(paths.config_path)
    current_provider = parse_current_provider(config_text)
    current_model = parse_current_model(config_text)
    provider_source = "config.toml:model_provider" if current_provider else None
    auth_mode = read_auth_mode(paths)

    with connect_db(paths.db_path, readonly=True) as conn:
        if not current_provider:
            current_provider, provider_source = infer_provider_from_auth(auth_mode)
        if not current_provider:
            current_provider, provider_source = infer_provider_from_threads(conn, current_model)
        if not current_provider:
            raise RuntimeError(
                "Could not determine the current provider from config.toml, auth.json, or recent threads."
            )

        counts = query_provider_counts(conn)
        threads = query_threads(conn)
        total_threads = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
        moved_if_sync = conn.execute(
            "SELECT COUNT(*) FROM threads WHERE model_provider <> ?",
            (current_provider,),
        ).fetchone()[0]
        session_meta_status = query_session_meta_counts(threads, current_provider)

    return {
        "platform": detect_platform(),
        "codex_home": str(paths.codex_home),
        "config_path": str(paths.config_path),
        "db_path": str(paths.db_path),
        "backup_dir": str(paths.backup_dir),
        "current_provider": current_provider,
        "current_provider_source": provider_source,
        "current_model": current_model,
        "auth_mode": auth_mode,
        "total_threads": total_threads,
        "movable_threads": moved_if_sync,
        "provider_counts": [{"provider": key, "count": value} for key, value in counts.items()],
        **session_meta_status,
        "backups": list_backups(paths),
    }


def make_backup(paths: Paths, label: str) -> Path:
    paths.backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = paths.backup_dir / f"state_5.sqlite.{label}.{timestamp}.bak"
    with connect_db(paths.db_path, readonly=True) as source, connect_db(backup_path, readonly=False) as target:
        source.backup(target)
    return backup_path


def make_session_meta_backup(backup_path: Path, threads: list[dict[str, object]]) -> Path:
    sidecar_path = backup_path.with_name(f"{backup_path.name}.session-meta.json")
    files = []
    seen_paths: set[Path] = set()

    for thread in threads:
        rollout_path = thread.get("rollout_path")
        if not isinstance(rollout_path, str) or not rollout_path:
            continue
        path = Path(rollout_path)
        if path in seen_paths or not path.exists():
            continue
        seen_paths.add(path)

        entries = iter_session_meta_prefix(path)
        if entries:
            files.append(
                {
                    "path": str(path),
                    "lines": [{"line_index": line_index, "text": line} for line_index, line, _ in entries],
                }
            )

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "files": files,
    }
    sidecar_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return sidecar_path


def build_session_meta_update_plan(
    threads: list[dict[str, object]], current_provider: str
) -> dict[str, object]:
    updates: list[dict[str, object]] = []
    missing_files: list[str] = []
    checked_files = 0
    seen_paths: set[Path] = set()

    for thread in threads:
        rollout_path = thread.get("rollout_path")
        if not isinstance(rollout_path, str) or not rollout_path:
            continue
        path = Path(rollout_path)
        if path in seen_paths:
            continue
        seen_paths.add(path)

        if not path.exists():
            missing_files.append(str(path))
            continue

        checked_files += 1
        line_updates: dict[int, str] = {}
        for line_index, original_line, payload in iter_session_meta_prefix(path):
            inner = payload.get("payload")
            if not isinstance(inner, dict):
                continue
            if inner.get("model_provider") == current_provider:
                continue
            inner["model_provider"] = current_provider
            newline = "\n" if original_line.endswith("\n") else ""
            line_updates[line_index] = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + newline

        if line_updates:
            updates.append({"path": path, "line_updates": line_updates})

    return {
        "checked_files": checked_files,
        "missing_files": missing_files,
        "updates": updates,
        "updated_session_files": len(updates),
        "updated_session_meta": sum(len(item["line_updates"]) for item in updates),
    }


def summarize_session_plan(plan: dict[str, object]) -> dict[str, object]:
    return {
        "checked_files": plan.get("checked_files", 0),
        "missing_files": len(plan.get("missing_files", [])),
        "missing_file_paths": plan.get("missing_files", []),
        "updated_session_files": plan.get("updated_session_files", 0),
        "updated_session_meta": plan.get("updated_session_meta", 0),
    }


def preflight_sync(paths: Paths, require_codex_closed: bool = True) -> dict[str, object]:
    issues: list[str] = []
    warnings: list[str] = []
    status: dict[str, object] | None = None
    session_plan: dict[str, object] | None = None
    columns: list[str] = []
    env_ok = True

    try:
        ensure_environment(paths)
    except Exception as exc:
        issues.append(str(exc))
        env_ok = False

    process_state = detect_codex_processes()
    if require_codex_closed and process_state["running"]:
        names = ", ".join(f"{p.get('name')}({p.get('pid')})" for p in process_state["processes"])
        issues.append(f"Codex is still running. Close it before syncing. Processes: {names}")

    if env_ok:
        try:
            with connect_db(paths.db_path, readonly=True) as conn:
                columns = validate_threads_schema(conn)
                quick_check = conn.execute("PRAGMA quick_check").fetchone()
                if quick_check and quick_check[0] != "ok":
                    issues.append(f"SQLite quick_check failed: {quick_check[0]}")
        except Exception as exc:
            issues.append(f"Database check failed: {exc}")

    if env_ok:
        try:
            status = get_status(paths)
        except Exception as exc:
            issues.append(f"Status check failed: {exc}")

    if env_ok:
        try:
            check_backup_dir_writable(paths)
        except Exception as exc:
            issues.append(f"Backup directory is not writable: {exc}")

    if env_ok:
        try:
            check_database_writable(paths)
        except Exception as exc:
            issues.append(f"Database is not writable or is locked: {exc}")

    if status:
        try:
            with connect_db(paths.db_path, readonly=True) as conn:
                threads = query_threads(conn)
            session_plan = build_session_meta_update_plan(threads, str(status["current_provider"]))
            missing_files = session_plan.get("missing_files", [])
            if missing_files:
                preview = ", ".join(str(item) for item in missing_files[:5])
                suffix = "" if len(missing_files) <= 5 else f" ... and {len(missing_files) - 5} more"
                issues.append(f"Missing session history files: {preview}{suffix}")
            rewrite_issues = []
            for item in session_plan["updates"]:
                try:
                    check_rewrite_target(item["path"])
                except Exception as exc:
                    rewrite_issues.append(f"{item['path']}: {exc}")
            if rewrite_issues:
                preview = " | ".join(rewrite_issues[:5])
                suffix = "" if len(rewrite_issues) <= 5 else f" | ... and {len(rewrite_issues) - 5} more"
                issues.append(f"Session files are not writable: {preview}{suffix}")
        except Exception as exc:
            issues.append(f"Session file check failed: {exc}")

    can_sync = not issues
    return {
        "action": "preflight",
        "can_sync": can_sync,
        "issues": issues,
        "warnings": warnings,
        "processes": process_state,
        "schema_columns": columns,
        "status": status,
        "session_plan": summarize_session_plan(session_plan) if session_plan else None,
    }


def get_current_provider_for_repair(paths: Paths, conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    current_provider: str | None = None
    provider_source: str | None = None

    if paths.config_path.exists():
        try:
            config_text = read_text(paths.config_path)
            current_provider = parse_current_provider(config_text)
            provider_source = "config.toml:model_provider" if current_provider else None
        except OSError:
            pass

    if not current_provider:
        auth_provider, auth_source = infer_provider_from_auth(read_auth_mode(paths))
        current_provider = auth_provider
        provider_source = auth_source

    if not current_provider:
        try:
            current_model = parse_current_model(read_text(paths.config_path)) if paths.config_path.exists() else None
        except OSError:
            current_model = None
        current_provider, provider_source = infer_provider_from_threads(conn, current_model)

    return current_provider, provider_source


def public_recovered_session(info: dict[str, object]) -> dict[str, object]:
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "provider": info.get("model_provider"),
        "rollout_path": info.get("rollout_path"),
        "updated_at": info.get("updated_at"),
        "session_meta_count": info.get("session_meta_count"),
    }


def diagnose_database(paths: Paths) -> dict[str, object]:
    issues: list[str] = []
    warnings: list[str] = []
    schema_columns: list[str] = []
    quick_check: str | None = None
    total_threads = 0
    current_provider: str | None = None
    provider_source: str | None = None
    provider_rows_to_sync = 0
    session_meta_status: dict[str, object] | None = None
    missing_session_files: list[str] = []
    empty_text_records = 0
    missing_thread_records: list[dict[str, object]] = []

    try:
        ensure_environment(paths)
    except Exception as exc:
        issues.append(str(exc))

    process_state = detect_codex_processes()
    scan = scan_session_history(paths)

    if paths.db_path.exists():
        try:
            with connect_db(paths.db_path, readonly=True, timeout=5) as conn:
                schema_columns = validate_threads_schema(conn)
                check_row = conn.execute("PRAGMA quick_check").fetchone()
                quick_check = str(check_row[0]) if check_row else None
                if quick_check != "ok":
                    issues.append(f"SQLite quick_check failed: {quick_check}")

                current_provider, provider_source = get_current_provider_for_repair(paths, conn)
                total_threads = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
                existing_ids = {
                    str(row[0])
                    for row in conn.execute("SELECT id FROM threads")
                    if row[0] is not None
                }

                threads = query_threads(conn)
                for thread in threads:
                    rollout_path = thread.get("rollout_path")
                    if isinstance(rollout_path, str) and rollout_path and not Path(rollout_path).exists():
                        missing_session_files.append(rollout_path)

                if current_provider:
                    provider_rows_to_sync = conn.execute(
                        "SELECT COUNT(*) FROM threads WHERE model_provider <> ?",
                        (current_provider,),
                    ).fetchone()[0]
                    session_meta_status = query_session_meta_counts(threads, current_provider)

                text_columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(threads)").fetchall()
                    if row[1] in {"title", "preview", "first_user_message"}
                }
                if text_columns:
                    clauses = [f"{column} = ''" for column in sorted(text_columns)]
                    clauses.extend(f"{column} IS NULL" for column in sorted(text_columns))
                    empty_text_records = conn.execute(
                        f"SELECT COUNT(*) FROM threads WHERE {' OR '.join(clauses)}"
                    ).fetchone()[0]

                for info in scan["sessions"]:
                    if str(info.get("id")) not in existing_ids:
                        missing_thread_records.append(public_recovered_session(info))
        except Exception as exc:
            issues.append(f"Database diagnosis failed: {exc}")
    else:
        issues.append(f"Database file does not exist: {paths.db_path}")

    if scan["unreadable_files"]:
        preview = ", ".join(scan["unreadable_files"][:5])
        warnings.append(f"Unreadable session files: {preview}")
    if scan["malformed_files"]:
        warnings.append(f"Malformed JSONL lines found in {len(scan['malformed_files'])} session files.")

    repairable = (
        paths.db_path.exists()
        and quick_check == "ok"
        and not any(item.startswith("Database diagnosis failed") for item in issues)
    )

    recommendations: list[str] = []
    if quick_check and quick_check != "ok":
        recommendations.append("SQLite integrity failed; restore a known-good backup before repairing indexes.")
    if missing_thread_records:
        recommendations.append("Run repair to rebuild missing thread index rows from JSONL session history.")
    if empty_text_records:
        recommendations.append("Run repair to fill empty titles/previews from the first user message in JSONL.")
    if provider_rows_to_sync or (session_meta_status and session_meta_status.get("mismatched_session_meta")):
        recommendations.append("Run repair or sync to align database rows and JSONL session_meta providers.")
    if missing_session_files:
        recommendations.append("Some database rows point to missing JSONL files; restore those files from backups if possible.")

    return {
        "action": "diagnose",
        "repairable": repairable,
        "issues": issues,
        "warnings": warnings,
        "processes": process_state,
        "platform": detect_platform(),
        "codex_home": str(paths.codex_home),
        "db_path": str(paths.db_path),
        "backup_dir": str(paths.backup_dir),
        "schema_columns": schema_columns,
        "quick_check": quick_check,
        "current_provider": current_provider,
        "current_provider_source": provider_source,
        "total_threads": total_threads,
        "session_files_found": scan["files_found"],
        "recoverable_sessions": len(scan["sessions"]),
        "missing_thread_records": len(missing_thread_records),
        "missing_thread_samples": missing_thread_records[:20],
        "empty_text_records": empty_text_records,
        "provider_rows_to_sync": provider_rows_to_sync,
        "missing_session_files": len(missing_session_files),
        "missing_session_file_samples": missing_session_files[:20],
        "session_meta_status": session_meta_status,
        "malformed_files": scan["malformed_files"][:20],
        "recommendations": recommendations,
    }


def text_value(value: object, default: str = "") -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


def int_value(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value))
    except Exception:
        return default


def build_recovered_thread_row(
    info: dict[str, object], columns: set[str], current_provider: str | None
) -> dict[str, object]:
    provider = text_value(info.get("model_provider") or current_provider or "openai", "openai")
    title = text_value(info.get("title"), "Recovered session") or "Recovered session"
    preview = text_value(info.get("preview"), title) or title
    first_user_message = text_value(info.get("first_user_message"), preview) or preview

    row = {
        "id": text_value(info.get("id")),
        "rollout_path": text_value(info.get("rollout_path")),
        "created_at": int_value(info.get("created_at"), int(time.time())),
        "updated_at": int_value(info.get("updated_at"), int(time.time())),
        "source": text_value(info.get("source"), "local") or "local",
        "model_provider": provider,
        "cwd": text_value(info.get("cwd")),
        "title": title,
        "sandbox_policy": text_value(info.get("sandbox_policy"), "workspace-write") or "workspace-write",
        "approval_mode": text_value(info.get("approval_mode"), "on-request") or "on-request",
        "tokens_used": 0,
        "has_user_event": int_value(info.get("has_user_event"), 0),
        "archived": int_value(info.get("archived"), 0),
        "archived_at": None,
        "git_sha": None,
        "git_branch": None,
        "git_origin_url": None,
        "cli_version": text_value(info.get("cli_version")),
        "first_user_message": first_user_message,
        "agent_nickname": None,
        "agent_role": None,
        "memory_mode": "enabled",
        "model": text_value(info.get("model")) or None,
        "reasoning_effort": None,
        "agent_path": None,
        "created_at_ms": int_value(info.get("created_at_ms"), int(time.time() * 1000)),
        "updated_at_ms": int_value(info.get("updated_at_ms"), int(time.time() * 1000)),
        "thread_source": text_value(info.get("thread_source")) or None,
        "preview": preview,
    }
    return {key: value for key, value in row.items() if key in columns}


def insert_recovered_thread(
    conn: sqlite3.Connection, columns: set[str], info: dict[str, object], current_provider: str | None
) -> None:
    row = build_recovered_thread_row(info, columns, current_provider)
    names = list(row.keys())
    placeholders = ", ".join("?" for _ in names)
    conn.execute(
        f"INSERT INTO threads ({', '.join(names)}) VALUES ({placeholders})",
        [row[name] for name in names],
    )


def repair_existing_thread_text(
    conn: sqlite3.Connection, columns: set[str], sessions_by_id: dict[str, dict[str, object]]
) -> int:
    if not {"id", "title", "preview", "first_user_message"} & columns:
        return 0

    updated = 0
    select_columns = ["id"]
    for column in ("title", "preview", "first_user_message"):
        if column in columns:
            select_columns.append(column)

    for row in conn.execute(f"SELECT {', '.join(select_columns)} FROM threads").fetchall():
        values = dict(zip(select_columns, row))
        info = sessions_by_id.get(str(values["id"]))
        if not info:
            continue

        updates: dict[str, object] = {}
        title = text_value(info.get("title"), "Recovered session")
        preview = text_value(info.get("preview"), title)
        first_user_message = text_value(info.get("first_user_message"), preview)

        if "title" in columns and (not values.get("title") or values.get("title") == "Recovered session"):
            updates["title"] = title or "Recovered session"
        if "preview" in columns and not values.get("preview"):
            updates["preview"] = preview or title or "Recovered session"
        if "first_user_message" in columns and not values.get("first_user_message"):
            updates["first_user_message"] = first_user_message or preview or title or "Recovered session"

        if updates:
            assignments = ", ".join(f"{column} = ?" for column in updates)
            conn.execute(
                f"UPDATE threads SET {assignments} WHERE id = ?",
                [*updates.values(), values["id"]],
            )
            updated += 1

    return updated


def repair_database(paths: Paths) -> dict[str, object]:
    ensure_codex_not_running()
    ensure_environment(paths)

    with connect_db(paths.db_path, readonly=True, timeout=5) as conn:
        validate_threads_schema(conn)
        quick_check = conn.execute("PRAGMA quick_check").fetchone()
        if not quick_check or quick_check[0] != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {quick_check[0] if quick_check else 'unknown'}")
        current_provider, provider_source = get_current_provider_for_repair(paths, conn)
        threads_before = query_threads(conn)

    scan = scan_session_history(paths)
    sessions = [item for item in scan["sessions"] if item.get("id")]
    sessions_by_id = {str(item["id"]): item for item in sessions}

    backup_path = make_backup(paths, "pre-repair")
    backup_threads = [*threads_before, *({"rollout_path": item.get("rollout_path")} for item in sessions)]
    session_backup_path = make_session_meta_backup(backup_path, backup_threads)
    rollback_result: dict[str, object] | None = None

    inserted_threads = 0
    updated_text_threads = 0
    normalized_provider_rows = 0
    session_update: dict[str, object] = {
        "updated_session_files": 0,
        "updated_session_meta": 0,
        "missing_session_files": 0,
    }
    checkpoint_result = (0, 0, 0)

    try:
        with connect_db(paths.db_path, readonly=False) as conn:
            conn.execute("BEGIN IMMEDIATE")
            table_info = conn.execute("PRAGMA table_info(threads)").fetchall()
            columns = {str(row[1]) for row in table_info}
            existing_ids = {
                str(row[0])
                for row in conn.execute("SELECT id FROM threads")
                if row[0] is not None
            }

            for info in sessions:
                session_id = str(info["id"])
                if session_id in existing_ids:
                    continue
                insert_recovered_thread(conn, columns, info, current_provider)
                existing_ids.add(session_id)
                inserted_threads += 1

            updated_text_threads = repair_existing_thread_text(conn, columns, sessions_by_id)

            if current_provider:
                normalized_provider_rows = conn.execute(
                    "UPDATE threads SET model_provider = ? WHERE model_provider <> ?",
                    (current_provider, current_provider),
                ).rowcount

            conn.commit()
            checkpoint_result = checkpoint(conn)

        if current_provider:
            with connect_db(paths.db_path, readonly=True) as conn:
                threads_after_db = query_threads(conn)
            session_plan = build_session_meta_update_plan(threads_after_db, current_provider)
            session_update = apply_session_meta_update_plan({**session_plan, "missing_files": []})
            session_update["missing_session_files"] = len(session_plan.get("missing_files", []))

        status_after = get_status(paths)
    except Exception as exc:
        rollback_errors: list[str] = []
        try:
            restore_sqlite_backup(paths, backup_path)
        except Exception as rollback_exc:
            rollback_errors.append(f"SQLite rollback failed: {rollback_exc}")
        try:
            rollback_result = restore_session_meta_backup(backup_path)
        except Exception as rollback_exc:
            rollback_errors.append(f"session metadata rollback failed: {rollback_exc}")
        if rollback_errors:
            raise RuntimeError(
                f"Repair failed and rollback was incomplete. Original error: {exc}. "
                f"{' | '.join(rollback_errors)}. Backup: {backup_path}"
            ) from exc
        raise RuntimeError(f"Repair failed and changes were rolled back. Original error: {exc}. Backup: {backup_path}") from exc

    return {
        "action": "repair",
        "current_provider": current_provider,
        "current_provider_source": provider_source,
        "backup_path": str(backup_path),
        "session_meta_backup_path": str(session_backup_path),
        "scanned_session_files": scan["files_found"],
        "recoverable_sessions": len(sessions),
        "inserted_threads": inserted_threads,
        "updated_text_threads": updated_text_threads,
        "normalized_provider_rows": normalized_provider_rows,
        "malformed_files": scan["malformed_files"][:20],
        **session_update,
        "checkpoint": {
            "busy": checkpoint_result[0],
            "log_frames": checkpoint_result[1],
            "checkpointed_frames": checkpoint_result[2],
        },
        "status": status_after,
        "rollback": rollback_result,
    }


def is_access_denied(error: OSError) -> bool:
    return (
        isinstance(error, PermissionError)
        or getattr(error, "winerror", None) == 5
        or getattr(error, "errno", None) in {errno.EACCES, errno.EPERM}
    )


def rewrite_text_lines(path: Path, line_updates: dict[int, str]) -> None:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as source:
        original_lines = list(source)

    fd, tmp_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as target:
            for line_index, line in enumerate(original_lines):
                target.write(line_updates.get(line_index, line))
        tmp_path.replace(path)
    except OSError as replace_error:
        if is_access_denied(replace_error):
            content = tmp_path.read_text(encoding="utf-8")
            tmp_path.unlink(missing_ok=True)
            try:
                with path.open("w", encoding="utf-8", newline="") as target:
                    target.write(content)
            except OSError as write_error:
                raise RuntimeError(
                    "Failed to write session history. Codex may still be holding the file open, "
                    f"or the file permissions are restrictive. Check that Codex is closed and retry: {path}"
                ) from write_error
        else:
            tmp_path.unlink(missing_ok=True)
            raise
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def update_session_meta_files(
    threads: list[dict[str, object]], current_provider: str
) -> dict[str, object]:
    plan = build_session_meta_update_plan(threads, current_provider)
    return apply_session_meta_update_plan(plan)


def apply_session_meta_update_plan(plan: dict[str, object]) -> dict[str, object]:
    missing_files = plan.get("missing_files", [])
    if missing_files:
        raise RuntimeError(f"Cannot update session metadata because {len(missing_files)} session files are missing.")

    updated_files = 0
    updated_session_meta = 0
    for item in plan.get("updates", []):
        path = item["path"]
        line_updates = item["line_updates"]
        rewrite_text_lines(path, line_updates)
        updated_files += 1
        updated_session_meta += len(line_updates)

    return {
        "updated_session_files": updated_files,
        "updated_session_meta": updated_session_meta,
        "missing_session_files": len(missing_files),
    }


def restore_session_meta_backup(backup_path: Path) -> dict[str, object]:
    sidecar_path = backup_path.with_name(f"{backup_path.name}.session-meta.json")
    if not sidecar_path.exists():
        return {"session_meta_restored": 0, "session_files_restored": 0, "session_meta_backup": None}

    payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    restored_files = 0
    restored_lines = 0

    for file_entry in payload.get("files", []):
        path = Path(file_entry.get("path", ""))
        lines = file_entry.get("lines", [])
        if not path.exists() or not isinstance(lines, list):
            continue
        line_updates = {
            int(item["line_index"]): item["text"]
            for item in lines
            if isinstance(item, dict) and "line_index" in item and "text" in item
        }
        if not line_updates:
            continue

        rewrite_text_lines(path, line_updates)

        restored_files += 1
        restored_lines += len(line_updates)

    return {
        "session_meta_backup": str(sidecar_path),
        "session_files_restored": restored_files,
        "session_meta_restored": restored_lines,
    }


def checkpoint(conn: sqlite3.Connection) -> tuple[int, int, int]:
    row = conn.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
    return int(row[0]), int(row[1]), int(row[2])


def restore_sqlite_backup(paths: Paths, backup_path: Path) -> tuple[int, int, int]:
    with connect_db(backup_path, readonly=True) as source, connect_db(paths.db_path, readonly=False) as target:
        source.backup(target)
        return checkpoint(target)


def sync_to_current_provider(paths: Paths) -> dict[str, object]:
    preflight = preflight_sync(paths, require_codex_closed=True)
    if not preflight["can_sync"]:
        raise RuntimeError("Preflight failed: " + " | ".join(preflight["issues"]))

    status_before = preflight["status"]
    current_provider: str = status_before["current_provider"]
    if not current_provider:
        raise RuntimeError("get_status() returned None for current_provider - this should not happen")
    with connect_db(paths.db_path, readonly=True) as conn:
        threads = query_threads(conn)
        before_counts = query_provider_counts(conn)
    session_plan = build_session_meta_update_plan(threads, current_provider)
    if session_plan["missing_files"]:
        raise RuntimeError("Preflight missed missing session files; aborting before writing.")

    backup_path = make_backup(paths, "pre-sync")
    session_backup_path = make_session_meta_backup(backup_path, threads)
    rollback_result: dict[str, object] | None = None

    try:
        session_update = apply_session_meta_update_plan(session_plan)
        with connect_db(paths.db_path, readonly=False) as conn:
            conn.execute("BEGIN IMMEDIATE")
            updated_rows = conn.execute(
                "UPDATE threads SET model_provider = ? WHERE model_provider <> ?",
                (current_provider, current_provider),
            ).rowcount
            conn.commit()
            checkpoint_result = checkpoint(conn)
        with connect_db(paths.db_path, readonly=True) as conn:
            after_counts = query_provider_counts(conn)

        status_after = get_status(paths)
        if status_after["movable_threads"] != 0 or status_after["mismatched_session_meta"] != 0:
            raise RuntimeError(
                "Sync verification failed after writing: "
                f"{status_after['movable_threads']} database rows and "
                f"{status_after['mismatched_session_meta']} session metadata entries still differ "
                f"from provider '{current_provider}'."
            )
    except Exception as exc:
        rollback_errors: list[str] = []
        try:
            restore_sqlite_backup(paths, backup_path)
        except Exception as rollback_exc:
            rollback_errors.append(f"SQLite rollback failed: {rollback_exc}")
        try:
            rollback_result = restore_session_meta_backup(backup_path)
        except Exception as rollback_exc:
            rollback_errors.append(f"session metadata rollback failed: {rollback_exc}")
        if rollback_errors:
            raise RuntimeError(
                f"Sync failed and rollback was incomplete. Original error: {exc}. "
                f"{' | '.join(rollback_errors)}. Backup: {backup_path}"
            ) from exc
        raise RuntimeError(f"Sync failed and changes were rolled back. Original error: {exc}. Backup: {backup_path}") from exc

    return {
        "action": "sync",
        "current_provider": current_provider,
        "updated_rows": updated_rows,
        "backup_path": str(backup_path),
        "session_meta_backup_path": str(session_backup_path),
        **session_update,
        "before_counts": [{"provider": key, "count": value} for key, value in before_counts.items()],
        "after_counts": [{"provider": key, "count": value} for key, value in after_counts.items()],
        "checkpoint": {
            "busy": checkpoint_result[0],
            "log_frames": checkpoint_result[1],
            "checkpointed_frames": checkpoint_result[2],
        },
        "status": status_after,
        "preflight": {
            "can_sync": preflight["can_sync"],
            "session_plan": preflight["session_plan"],
        },
        "rollback": rollback_result,
    }


def resolve_backup(paths: Paths, requested_path: str | None) -> Path:
    if requested_path:
        backup = Path(requested_path).expanduser()
    else:
        backups = list_backups(paths, limit=1)
        if not backups:
            raise RuntimeError("No backup files were found.")
        backup = Path(backups[0]["path"])
    if not backup.exists():
        raise RuntimeError(f"Backup file does not exist: {backup}")
    return backup


def restore_backup(paths: Paths, backup_path: str | None) -> dict[str, object]:
    ensure_codex_not_running()
    ensure_environment(paths)
    chosen_backup = resolve_backup(paths, backup_path)
    restore_snapshot = make_backup(paths, "pre-restore")
    with connect_db(paths.db_path, readonly=True) as conn:
        current_threads = query_threads(conn)
    restore_snapshot_sidecar = make_session_meta_backup(restore_snapshot, current_threads)

    with connect_db(chosen_backup, readonly=True) as source, connect_db(paths.db_path, readonly=False) as target:
        source.backup(target)
        checkpoint_result = checkpoint(target)
    session_restore = restore_session_meta_backup(chosen_backup)

    status_after = get_status(paths)
    return {
        "action": "restore",
        "restored_from": str(chosen_backup),
        "safety_backup": str(restore_snapshot),
        "safety_session_meta_backup": str(restore_snapshot_sidecar),
        "checkpoint": {
            "busy": checkpoint_result[0],
            "log_frames": checkpoint_result[1],
            "checkpointed_frames": checkpoint_result[2],
        },
        **session_restore,
        "status": status_after,
    }


def to_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def print_output(text: str) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(text)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Codex history sync helper")
    parser.add_argument("--codex-home", help="Override Codex home directory")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="Show current provider/thread status")
    subparsers.add_parser("detect", help="Detect platform and Codex paths")
    subparsers.add_parser("diagnose", help="Diagnose database/session-history repair needs")
    subparsers.add_parser("preflight", help="Check whether sync can safely run")
    subparsers.add_parser("processes", help="Check whether Codex is currently running")
    subparsers.add_parser("close-processes", help="Close detected Codex processes")
    subparsers.add_parser("sync", help="Move all thread providers to the current provider")
    subparsers.add_parser("repair", help="Repair recoverable database/session-history issues")
    restore_parser = subparsers.add_parser("restore", help="Restore from a backup")
    restore_parser.add_argument("--backup", help="Backup file path; newest backup is used when omitted")
    detail_parser = subparsers.add_parser("backup-detail", help="Show backup details")
    detail_parser.add_argument("--backup", required=True, help="Backup file path")
    delete_parser = subparsers.add_parser("delete-backup", help="Delete a backup and its session-meta sidecar")
    delete_parser.add_argument("--backup", required=True, help="Backup file path")
    subparsers.add_parser("backup", help="Create a manual backup")

    args = parser.parse_args()
    paths = resolve_paths(args.codex_home)

    try:
        if args.command == "status":
            payload = get_status(paths)
        elif args.command == "detect":
            payload = detect_codex_home(args.codex_home)
        elif args.command == "diagnose":
            payload = diagnose_database(paths)
        elif args.command == "preflight":
            payload = preflight_sync(paths)
        elif args.command == "processes":
            payload = detect_codex_processes()
        elif args.command == "close-processes":
            payload = close_codex_processes()
        elif args.command == "sync":
            payload = sync_to_current_provider(paths)
        elif args.command == "repair":
            payload = repair_database(paths)
        elif args.command == "restore":
            payload = restore_backup(paths, args.backup)
        elif args.command == "backup-detail":
            payload = inspect_backup(paths, args.backup)
        elif args.command == "delete-backup":
            payload = delete_backup(paths, args.backup)
        elif args.command == "backup":
            ensure_environment(paths)
            backup_path = make_backup(paths, "manual")
            with connect_db(paths.db_path, readonly=True) as conn:
                threads = query_threads(conn)
            session_backup_path = make_session_meta_backup(backup_path, threads)
            payload = {
                "action": "backup",
                "backup_path": str(backup_path),
                "session_meta_backup_path": str(session_backup_path),
            }
        else:
            raise RuntimeError(f"Unsupported command: {args.command}")
    except Exception as exc:
        error_payload = {"ok": False, "error": str(exc)}
        if args.json:
            print_output(to_json(error_payload))
        else:
            print_output(error_payload["error"])
        return 1

    if isinstance(payload, dict):
        payload["ok"] = True

    if args.json:
        print_output(to_json(payload))
    else:
        print_output(str(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
