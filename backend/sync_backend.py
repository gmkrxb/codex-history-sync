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


def connect_db(path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        uri_path = path.resolve().as_posix()
        return sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True, timeout=30)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def ensure_environment(paths: Paths) -> None:
    if not paths.config_path.exists():
        raise RuntimeError(f"Missing config file: {paths.config_path}")
    if not paths.db_path.exists():
        raise RuntimeError(f"Missing database file: {paths.db_path}")


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


def query_threads(conn: sqlite3.Connection) -> list[dict[str, object]]:
    rows = []
    for row in conn.execute(
        """
        SELECT id, rollout_path, title, model_provider, archived
        FROM threads
        ORDER BY updated_at DESC
        """
    ):
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


def iter_session_meta_prefix(path: Path, max_lines: int = 128) -> list[tuple[int, str, dict[str, object]]]:
    entries = []
    if not path.exists():
        return entries

    saw_meta = False
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_index, line in enumerate(handle):
                if line_index >= max_lines:
                    break
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    if saw_meta:
                        break
                    continue

                if payload.get("type") == "session_meta" and isinstance(payload.get("payload"), dict):
                    saw_meta = True
                    entries.append((line_index, line, payload))
                    continue

                if saw_meta:
                    break
    except OSError:
        return []

    return entries


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
    return [f"kill {' '.join(pids)}"]


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
            payload = json.loads(result.stdout)
            if isinstance(payload, dict):
                payload = [payload]
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        processes.append(
                            {
                                "pid": item.get("Id"),
                                "name": item.get("ProcessName"),
                                "path": item.get("Path"),
                                "kind": "helper" if str(item.get("ProcessName")).lower() == "node_repl" else "codex",
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
                            "kind": "helper" if name.lower() == "node_repl" else "codex",
                        }
                    )

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

        try:
            tmp_path.replace(path)
        except OSError as replace_error:
            if not is_access_denied(replace_error):
                raise
            content = tmp_path.read_text(encoding="utf-8")
            try:
                with path.open("w", encoding="utf-8", newline="") as target:
                    target.write(content)
            except OSError as write_error:
                raise RuntimeError(
                    "写入会话历史失败，Windows 拒绝替换或覆盖该 JSONL 文件。"
                    f"请确认 Codex 已关闭，并检查文件权限后重试：{path}"
                ) from write_error
            finally:
                tmp_path.unlink(missing_ok=True)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def update_session_meta_files(
    threads: list[dict[str, object]], current_provider: str
) -> dict[str, object]:
    updated_files = 0
    updated_session_meta = 0
    missing_files = 0
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

        metas = iter_session_meta_prefix(path)
        line_updates: dict[int, str] = {}
        for line_index, original_line, payload in metas:
            inner = payload.get("payload")
            if not isinstance(inner, dict):
                continue
            if inner.get("model_provider") == current_provider:
                continue
            inner["model_provider"] = current_provider
            newline = "\n" if original_line.endswith("\n") else ""
            line_updates[line_index] = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + newline

        if not line_updates:
            continue

        rewrite_text_lines(path, line_updates)

        updated_files += 1
        updated_session_meta += len(line_updates)

    return {
        "updated_session_files": updated_files,
        "updated_session_meta": updated_session_meta,
        "missing_session_files": missing_files,
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


def sync_to_current_provider(paths: Paths) -> dict[str, object]:
    ensure_codex_not_running()
    status_before = get_status(paths)
    current_provider = status_before["current_provider"]
    backup_path = make_backup(paths, "pre-sync")
    with connect_db(paths.db_path, readonly=True) as conn:
        threads = query_threads(conn)
    session_backup_path = make_session_meta_backup(backup_path, threads)
    session_update = update_session_meta_files(threads, str(current_provider))
    with connect_db(paths.db_path, readonly=False) as conn:
        before_counts = query_provider_counts(conn)
        updated_rows = conn.execute(
            "UPDATE threads SET model_provider = ? WHERE model_provider <> ?",
            (current_provider, current_provider),
        ).rowcount
        conn.commit()
        checkpoint_result = checkpoint(conn)
        after_counts = query_provider_counts(conn)
    status_after = get_status(paths)
    if status_after["movable_threads"] != 0 or status_after["mismatched_session_meta"] != 0:
        raise RuntimeError(
            "Sync finished writing, but verification still found "
            f"{status_after['movable_threads']} database rows and "
            f"{status_after['mismatched_session_meta']} session metadata entries outside "
            f"the current provider '{current_provider}'. Backup: {backup_path}"
        )

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

    with connect_db(chosen_backup, readonly=True) as source, connect_db(paths.db_path, readonly=False) as target:
        source.backup(target)
        checkpoint_result = checkpoint(target)
    session_restore = restore_session_meta_backup(chosen_backup)

    status_after = get_status(paths)
    return {
        "action": "restore",
        "restored_from": str(chosen_backup),
        "safety_backup": str(restore_snapshot),
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
    subparsers.add_parser("processes", help="Check whether Codex is currently running")
    subparsers.add_parser("close-processes", help="Close detected Codex processes")
    subparsers.add_parser("sync", help="Move all thread providers to the current provider")
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
        elif args.command == "processes":
            payload = detect_codex_processes()
        elif args.command == "close-processes":
            payload = close_codex_processes()
        elif args.command == "sync":
            payload = sync_to_current_provider(paths)
        elif args.command == "restore":
            payload = restore_backup(paths, args.backup)
        elif args.command == "backup-detail":
            payload = inspect_backup(paths, args.backup)
        elif args.command == "delete-backup":
            payload = delete_backup(paths, args.backup)
        elif args.command == "backup":
            ensure_environment(paths)
            payload = {"action": "backup", "backup_path": str(make_backup(paths, "manual"))}
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
