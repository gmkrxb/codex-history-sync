# Codex History Sync

<p align="center">
  <img src="assets/codex-sync-modern.png" alt="Codex History Sync icon" width="120" />
</p>

<p align="center">
  <strong>修复 Codex Desktop 本地历史不可见、同步不完整、数据库索引异常和备份恢复问题。</strong>
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
  <a href="README_EN.md">English</a> ·
  <a href="#下载">下载</a> ·
  <a href="#30-更新内容">3.0 更新内容</a> ·
  <a href="#命令行">命令行</a> ·
  <a href="#发布-300">发布 3.0.0</a>
</p>

![概览](docs/screenshots/overview.png)

## 简介

Codex History Sync 是一个用于修复 Codex Desktop 本地历史显示问题的桌面工具。常见场景是：切换账号、API Key、认证方式或 `model_provider` 后，历史对话仍然保存在 `~/.codex`，但 Codex Desktop 左侧历史列表不再显示或只显示一部分。

3.0.0 版本在 2.0 GUI 的基础上重点修复了同步不完整、JSONL 元数据只改一部分、写入失败误判成功、恢复备份不完整等问题，并新增数据库诊断/修复、同步前环境预检、失败后管理员权限重试、GitHub Release 更新检测。

项目地址：[gmkrxb/codex-history-sync](https://github.com/gmkrxb/codex-history-sync)

## 3.0 更新内容

- 同步前完整预检：检查 Codex 进程、SQLite schema、`PRAGMA quick_check`、备份目录写入权限、数据库锁、JSONL 文件读写权限。
- 修复同步不完整：完整扫描 JSONL 中所有 `session_meta`，不再只扫描文件开头，也不再漏掉同文件里的多条元数据。
- 写后校验和回滚：同步后再次检查 DB 与 JSONL 是否全部归到当前 provider；失败时尝试恢复 SQLite 与 JSONL 备份。
- 数据库诊断：检测数据库完整性、缺失 threads 索引、空标题/预览、缺失 JSONL、provider 不一致和 JSONL 解析异常。
- 数据库修复：从 `sessions/` 与 `archived_sessions/` 的 JSONL 重建缺失的 `threads` 记录，补空标题/预览，修正 provider 元数据。修复策略默认“只补不删”。
- 管理员权限重试：同步、恢复、修复失败后，可在界面点击获取管理员权限继续；Windows 使用 UAC，macOS 使用管理员授权，Linux 优先使用 `pkexec`。
- 更新检测：应用启动后有网络就检查 GitHub Releases，不强制更新；有新版本时显示小点提示，用户点击后可查看更新说明并跳转 Release 页面。
- UI 文案修复：恢复中文界面与 README 编码，补齐 GitHub 链接、操作日志和修复结果展示。

## 适用场景

适合这些情况：

- 切换账号、API Key、认证方式或 provider 后，Codex Desktop 历史突然不可见。
- 同步后只恢复了一部分历史，或者 JSONL 与 SQLite provider 不一致。
- 本地 `~/.codex/state_5.sqlite` 仍存在，但历史索引记录缺失、标题为空、预览为空。
- 使用过不稳定版本，担心数据库索引或历史元数据被写坏。
- 需要先看到同步/修复会改什么，再决定是否执行。

不适合这些情况：

- 多台电脑之间合并历史。
- 云端账号之间同步对话。
- SQLite 数据库文件已经完全删除且没有任何备份或 JSONL 历史。
- `PRAGMA quick_check` 已确认数据库底层损坏时直接强行写入；这种情况应先从备份恢复。

## 下载

Release 页面：[https://github.com/gmkrxb/codex-history-sync/releases](https://github.com/gmkrxb/codex-history-sync/releases)

| 系统 | 架构 | 类型 | 下载 |
| --- | --- | --- | --- |
| Windows | x64 | 安装包 | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Setup-3.0.0-win-x64.exe) |
| Windows | x64 | 便携版 EXE | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Portable-3.0.0-win-x64.exe) |
| Windows | arm64 | 安装包 | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Setup-3.0.0-win-arm64.exe) |
| Windows | arm64 | 便携版 EXE | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Portable-3.0.0-win-arm64.exe) |
| macOS | Intel x64 | DMG | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-mac-x64.dmg) |
| macOS | Apple Silicon arm64 | DMG | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-mac-arm64.dmg) |
| Linux | x64 | AppImage | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-linux-x86_64.AppImage) |
| Linux | x64 | deb | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-linux-amd64.deb) |
| Linux | arm64 | AppImage | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-linux-arm64.AppImage) |
| Linux | arm64 | deb | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-3.0.0-linux-arm64.deb) |

Release 产物由 GitHub Actions 自动构建并上传。

## 使用建议

1. 先关闭 Codex Desktop。
2. 打开 Codex History Sync，查看概览页状态。
3. 如果只是 provider 不一致，进入“历史同步”执行同步。
4. 如果历史记录缺失、标题为空、同步结果异常，先在“概览”执行“诊断数据库”，再执行“修复数据库”。
5. 同步、修复、恢复失败且错误指向权限不足时，点击“获取管理员权限后重试”。
6. 任意写入操作前都会自动创建备份；仍建议不要在 Codex 正在运行时写入。

## 快速开始

```powershell
git clone https://github.com/gmkrxb/codex-history-sync.git
cd codex-history-sync
npm install
npm run electron:dev
```

只构建前端：

```powershell
npm run build
```

打包当前平台：

```powershell
npm run electron:build
```

## 命令行

后端入口：

```powershell
py -3 backend\sync_backend.py [全局参数] <命令> [命令参数]
```

macOS / Linux：

```bash
python3 backend/sync_backend.py [global options] <command> [command options]
```

### 全局参数

| 参数 | 说明 |
| --- | --- |
| `--json` | 输出 JSON，Electron 与脚本集成推荐使用。 |
| `--codex-home <path>` | 指定 Codex 数据目录，默认使用当前用户的 `~/.codex`。 |

### 命令

| 命令 | 参数 | 说明 |
| --- | --- | --- |
| `status` | 无 | 读取当前 provider、模型、线程数量、provider 分布、JSONL 元数据状态和备份列表。 |
| `detect` | 无 | 检测系统、Codex home、配置文件、认证文件和数据库路径。 |
| `diagnose` | 无 | 诊断数据库完整性、缺失索引、空标题/预览、JSONL 元数据和 provider 不一致问题。 |
| `preflight` | 无 | 同步前预检，检查 Codex 进程、DB/schema、备份目录和 JSONL 可写性。 |
| `processes` | 无 | 检测 Codex 或辅助进程是否仍在运行。 |
| `close-processes` | 无 | 尝试关闭检测到的 Codex 相关进程；失败时返回手动命令。 |
| `sync` | 无 | 将 SQLite 与 JSONL provider 同步到当前 provider，写入前备份，写入后校验。 |
| `repair` | 无 | 从 JSONL 重建缺失索引、补标题/预览、修正 provider；执行前备份。 |
| `backup` | 无 | 手动创建 SQLite 备份，并创建 JSONL 元数据 sidecar。 |
| `restore` | `--backup <path>` 可选 | 从备份恢复；不传 `--backup` 时使用最新备份。恢复前会再创建安全备份。 |
| `backup-detail` | `--backup <path>` 必填 | 查看备份详情，包括线程数、provider 分布和线程预览。 |
| `delete-backup` | `--backup <path>` 必填 | 删除指定 SQLite 备份和配套 JSONL 元数据备份。 |

### 示例

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

指定 Codex 数据目录：

```powershell
py -3 backend\sync_backend.py --codex-home "D:\CodexData\.codex" --json status
```

## 版本历史

### v3.0.0

- 修复同步失败、同步不完整、JSONL 元数据只同步部分的问题。
- 新增同步前环境预检、写后校验、失败回滚。
- 新增数据库诊断与修复功能。
- 新增同步/恢复/修复失败后的管理员权限重试。
- 新增 GitHub 链接和 Release 更新检测。
- 修复前端 API 调用、恢复备份 JSONL sidecar、Windows Python 选择等问题。

### v2.0.0

- 从命令行工具升级为 Vue 3 + Electron 桌面 GUI。
- 增加概览、历史同步、备份恢复、日志页面。
- 增加跨平台安装包：Windows、macOS、Linux 多架构产物。

### v1.0.0

- 初始版本，核心能力集中在 `backend/sync_backend.py`。
- 通过 Python CLI 读取 `~/.codex/state_5.sqlite` 并同步 provider。
- 适合手动运行命令修复历史显示问题。

## 发布 3.0.0

确认代码、README、`package.json` 与 `package-lock.json` 都是 `3.0.0` 后执行：

```powershell
git status
git add backend/sync_backend.py electron/main.js electron/preload.js src package.json package-lock.json README.md README_EN.md .github/workflows/release.yml
git commit -m "Release v3.0.0"
git tag v3.0.0
git push origin main
git push origin v3.0.0
```

推送 tag 后，GitHub Actions 会自动构建并发布 Release。也可以手动触发：

```powershell
gh workflow run release.yml -f tag=v3.0.0
```

## 安全说明

本工具会修改本地 Codex 数据。同步、修复和恢复都会先创建备份，但仍建议在写入前关闭 Codex Desktop。数据库底层损坏时，工具不会强行写入，应优先从备份恢复。

## 截图

### 概览

![概览](docs/screenshots/overview.png)

### 历史同步

![历史同步](docs/screenshots/sync.png)

### 进程保护

![进程保护](docs/screenshots/process-guard.png)

### 备份恢复

![备份恢复](docs/screenshots/backups.png)

### 备份详情

![备份详情](docs/screenshots/backup-detail.png)

## 项目结构

```text
.
├── assets/                 # 应用图标
├── backend/                # Python 后端，负责 SQLite/JSONL 同步、诊断、修复
├── electron/               # Electron main/preload
├── src/                    # Vue 3 渲染进程应用
├── docs/screenshots/       # README 截图
├── package.json            # 应用脚本与 electron-builder 配置
├── vite.config.js
├── README.md
├── README_EN.md
└── LICENSE
```

## License

MIT
