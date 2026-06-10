# Codex History Sync

<p align="center">
  <img src="assets/codex-sync-modern.png" alt="Codex History Sync icon" width="120" />
</p>

<p align="center">
  <strong>Repair invisible Codex Desktop history, partial syncs, broken local indexes, and backup recovery issues.</strong>
</p>

<p align="center">
  <a href="https://github.com/gmkrxb/codex-history-sync/actions/workflows/release.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/gmkrxb/codex-history-sync/release.yml?branch=main&label=build&logo=github" alt="Build status" />
  </a>
  <a href="https://github.com/gmkrxb/codex-history-sync/releases/latest">
    <img src="https://img.shields.io/github/v/release/gmkrxb/codex-history-sync?label=release" alt="Latest release" />
  </a>
  <img src="https://img.shields.io/github/package-json/v/gmkrxb/codex-history-sync?label=version" alt="Version" />
  <a href="https://github.com/gmkrxb/codex-history-sync/releases">
    <img src="https://img.shields.io/github/downloads/gmkrxb/codex-history-sync/total?label=downloads" alt="Downloads" />
  </a>
  <a href="https://github.com/gmkrxb/codex-history-sync/stargazers">
    <img src="https://img.shields.io/github/stars/gmkrxb/codex-history-sync?style=flat&label=stars" alt="Stars" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/gmkrxb/codex-history-sync?label=license" alt="License" />
  </a>
</p>

<p align="center">
  <a href="README.md">中文</a> ·
  <a href="#downloads">Downloads</a> ·
  <a href="#whats-new-in-300">What's New in 3.0</a> ·
  <a href="#cli">CLI</a> ·
  <a href="#release-300">Release 3.0.0</a>
</p>

![Overview](docs/screenshots/overview.png)

## Overview

Codex History Sync is a desktop utility for repairing Codex Desktop local history visibility. A common failure mode is: after switching accounts, API keys, auth modes, or `model_provider`, conversations still exist under `~/.codex`, but Codex Desktop shows no history or only part of it.

Version 3.0.0 builds on the 2.0 GUI release and focuses on reliability: partial JSONL syncs, false success states, incomplete restore behavior, database index gaps, environment preflight checks, elevated retry, and GitHub Release update checks.

Repository: [gmkrxb/codex-history-sync](https://github.com/gmkrxb/codex-history-sync)

## What's New in 3.0.0

- Full preflight before sync: Codex process guard, SQLite schema validation, `PRAGMA quick_check`, backup directory write test, database lock test, and JSONL rewrite permission checks.
- Fixed partial sync: scans every `session_meta` entry in JSONL files instead of only looking near the top of each file.
- Post-write verification and rollback: after sync, the backend verifies both SQLite and JSONL state; if verification fails, it attempts to restore the safety backups.
- Database diagnosis: detects SQLite integrity status, missing `threads` rows, empty titles/previews, missing JSONL files, provider mismatches, and malformed JSONL lines.
- Database repair: rebuilds missing `threads` rows from `sessions/` and `archived_sessions/`, fills empty titles/previews, and normalizes provider metadata. The repair strategy is conservative: add/fill/fix, never delete.
- Elevated retry: when sync, restore, or repair fails because of permissions, the UI can retry with administrator privileges. Windows uses UAC, macOS uses administrator authorization, and Linux uses `pkexec` when available.
- Update check: the app checks GitHub Releases when network is available, shows a small non-blocking indicator, displays release notes, and lets users open the Release page.
- UI/documentation cleanup: restored readable Chinese text, added GitHub links, repair result summaries, and clearer operation logs.

## When To Use

Use this tool when:

- Codex Desktop history disappears after switching account, API key, auth mode, or provider.
- Sync restores only part of the history.
- SQLite and JSONL provider metadata are inconsistent.
- `~/.codex/state_5.sqlite` still exists but local history index rows are missing or have empty titles/previews.
- You used an unstable version and want to diagnose or repair local history metadata.
- You want to preview sync/repair impact before writing.

Do not use it for:

- Merging histories across different machines.
- Syncing conversations between cloud accounts.
- Recovering a fully deleted SQLite database when there are no backups and no JSONL history files.
- Force-writing to a SQLite database that fails `PRAGMA quick_check`; restore a known-good backup first.

## Downloads

Release page: [https://github.com/gmkrxb/codex-history-sync/releases](https://github.com/gmkrxb/codex-history-sync/releases)

| Platform | Architecture | Package | Download |
| --- | --- | --- | --- |
| Windows | x64 | Installer | [Download](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Setup-3.0.0-win-x64.exe) |
| Windows | x64 | Portable EXE | [Download](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Portable-3.0.0-win-x64.exe) |
| Windows | arm64 | Installer | [Download](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Setup-3.0.0-win-arm64.exe) |
| Windows | arm64 | Portable EXE | [Download](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Portable-3.0.0-win-arm64.exe) |
| macOS | Intel x64 | DMG | [Download](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-mac-x64.dmg) |
| macOS | Apple Silicon arm64 | DMG | [Download](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-mac-arm64.dmg) |
| Linux | x64 | AppImage | [Download](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-linux-x86_64.AppImage) |
| Linux | x64 | deb | [Download](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-linux-amd64.deb) |
| Linux | arm64 | AppImage | [Download](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-linux-arm64.AppImage) |
| Linux | arm64 | deb | [Download](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-linux-arm64.deb) |

Release assets are built and uploaded by GitHub Actions.

## Recommended Workflow

1. Close Codex Desktop.
2. Open Codex History Sync and review the Overview page.
3. If only provider metadata differs, use the Sync page.
4. If history rows are missing, titles are empty, or previous syncs behaved oddly, run Database Diagnosis first, then Database Repair.
5. If sync, repair, or restore fails with a permission-related error, use the elevated retry button.
6. The app creates safety backups before every write, but writing while Codex is running is still discouraged.

## Quick Start

```powershell
git clone https://github.com/gmkrxb/codex-history-sync.git
cd codex-history-sync
npm install
npm run electron:dev
```

Build only the renderer:

```powershell
npm run build
```

Build the current platform package:

```powershell
npm run electron:build
```

## CLI

Backend entry point on Windows:

```powershell
py -3 backend\sync_backend.py [global options] <command> [command options]
```

macOS / Linux:

```bash
python3 backend/sync_backend.py [global options] <command> [command options]
```

### Global Options

| Option | Description |
| --- | --- |
| `--json` | Emit JSON output. Recommended for Electron integration and scripts. |
| `--codex-home <path>` | Override the Codex data directory. Defaults to the current user's `~/.codex`. |

### Commands

| Command | Options | Description |
| --- | --- | --- |
| `status` | None | Show current provider, model, thread counts, provider distribution, JSONL metadata status, and backup list. |
| `detect` | None | Detect platform, Codex home, config path, auth path, and SQLite database path. |
| `diagnose` | None | Diagnose database integrity, missing index rows, empty titles/previews, JSONL metadata, and provider mismatches. |
| `preflight` | None | Run pre-sync safety checks for Codex processes, DB/schema, backup directory, and JSONL writability. |
| `processes` | None | Check whether Codex or helper processes are still running. |
| `close-processes` | None | Try to close detected Codex-related processes and return manual fallback commands when needed. |
| `sync` | None | Sync SQLite and JSONL providers to the current provider. Creates backups before writing and verifies after writing. |
| `repair` | None | Rebuild missing index rows from JSONL, fill empty titles/previews, and normalize provider metadata. Creates backups first. |
| `backup` | None | Create a manual SQLite backup plus JSONL metadata sidecar. |
| `restore` | `--backup <path>` optional | Restore from a backup. Uses the newest backup when omitted and creates a safety backup first. |
| `backup-detail` | `--backup <path>` required | Show backup details, including thread count, provider distribution, and thread preview. |
| `delete-backup` | `--backup <path>` required | Delete a SQLite backup and its JSONL session metadata sidecar. |

### Examples

```powershell
py -3 backend\sync_backend.py --json status
py -3 backend\sync_backend.py --json diagnose
py -3 backend\sync_backend.py --json preflight
py -3 backend\sync_backend.py --json sync
py -3 backend\sync_backend.py --json repair
py -3 backend\sync_backend.py --json backup
py -3 backend\sync_backend.py --json restore
py -3 backend\sync_backend.py --json restore --backup "C:\Users\you\.codex\history_sync_backups\state_5.sqlite.pre-sync.20260610-120000.bak"
```

Use a custom Codex home:

```powershell
py -3 backend\sync_backend.py --codex-home "D:\CodexData\.codex" --json status
```

## Version History

### v3.0.0

- Fixed sync failures, partial syncs, and JSONL metadata mismatch issues.
- Added preflight checks, post-write verification, and rollback.
- Added database diagnosis and repair.
- Added elevated retry for sync, restore, and repair.
- Added GitHub link and Release update check.
- Fixed frontend API wiring, JSONL sidecar restore handling, Windows Python selection, and Chinese documentation/UI text.

### v2.0.0

- Upgraded from a CLI helper to a Vue 3 + Electron desktop GUI.
- Added Overview, Sync, Backup/Restore, and Logs pages.
- Added cross-platform packages for Windows, macOS, and Linux.

### v1.0.0

- Initial backend-only version centered on `backend/sync_backend.py`.
- Used a Python CLI to inspect `~/.codex/state_5.sqlite` and sync provider metadata.
- Best suited for manual command-line repair.

## Release 3.0.0

After confirming `package.json`, `package-lock.json`, README files, and code changes are ready:

```powershell
git status
git add backend/sync_backend.py electron/main.js electron/preload.js src package.json package-lock.json README.md README_EN.md .github/workflows/release.yml
git commit -m "Release v3.0.0"
git tag v3.0.0
git push origin main
git push origin v3.0.0
```

Pushing the tag starts GitHub Actions and publishes the Release automatically. You can also trigger it manually:

```powershell
gh workflow run release.yml -f tag=v3.0.0
```

## Safety Notes

This tool modifies local Codex data. Sync, repair, and restore operations create backups first, but you should still close Codex Desktop before writing. If SQLite integrity checks fail, do not force-write; restore a known-good backup first.

## Screenshots

### Overview

![Overview](docs/screenshots/overview.png)

### Sync

![Sync](docs/screenshots/sync.png)

### Process Guard

![Process Guard](docs/screenshots/process-guard.png)

### Backups

![Backups](docs/screenshots/backups.png)

### Backup Detail

![Backup Detail](docs/screenshots/backup-detail.png)

## Project Structure

```text
.
├── assets/                 # Application icons
├── backend/                # Python backend for SQLite/JSONL sync, diagnosis, and repair
├── electron/               # Electron main/preload process
├── src/                    # Vue 3 renderer application
├── docs/screenshots/       # README screenshots
├── package.json            # App scripts and electron-builder config
├── vite.config.js
├── README.md
├── README_EN.md
└── LICENSE
```

## License

MIT
