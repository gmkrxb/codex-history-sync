# Codex History Sync

<p align="center">
  <img src="assets/codex-sync-modern.png" alt="Codex History Sync icon" width="120" />
</p>

<p align="center">
  <strong>在切换账号、API Key 或 provider 后，修复 Codex Desktop 本地历史列表不可见的问题。</strong>
</p>

<p align="center">
  <a href="README_EN.md">English</a> ·
  <a href="#下载">下载</a> ·
  <a href="#截图">截图</a> ·
  <a href="#快速开始">快速开始</a>
</p>

![概览](docs/screenshots/overview.png)

## 简介

Codex History Sync 是一个用于修复 Codex Desktop 本地历史显示问题的桌面工具。常见场景是：你切换了账号、API Key、认证方式或 `model_provider` 之后，历史对话其实还在 `~/.codex` 里，但 Codex Desktop 左侧历史列表不再展示。

这个工具会读取本机 Codex 配置和 SQLite 数据库，展示 provider 分布，自动创建备份，并把旧 provider 下的历史记录同步到当前正在使用的 provider。同时它也会同步 JSONL 会话文件里的 `session_meta.payload.model_provider`，避免数据库索引和原始会话文件不一致。

## 功能

- 支持 Windows 和 macOS 的本地路径自动检测。
- 自动识别 `~/.codex`、`config.toml`、`auth.json` 和 `state_5.sqlite`。
- 展示本地 `threads` 记录的 provider 分布。
- 将 SQLite 中的 `threads.model_provider` 同步到当前 provider。
- 将 JSONL 中的 `session_meta.payload.model_provider` 同步到当前 provider。
- 同步前和恢复前自动备份 SQLite 与 JSONL 元数据。
- 备份详情弹窗，支持查看 provider 统计和线程预览。
- 备份删除需要二次确认。
- 同步前检测 Codex 进程，支持一键关闭和手动命令兜底。
- Windows 终端下使用 UTF-8 输出，避免中文或特殊字符导致编码失败。

## 适用场景

适合这些情况：

- 切换账号、API Key、认证方式或 provider 后，Codex Desktop 历史突然不可见。
- 本地 `~/.codex` 目录仍然存在。
- `state_5.sqlite` 数据库仍然存在且可读取。
- 你希望先看清 provider 分布，再决定是否同步。

不适合这些情况：

- 多台电脑之间合并历史。
- 云端账号之间互相同步对话。
- 本地 SQLite 数据库已经被删除或损坏。

## 下载

| 系统 | 架构 | 类型 | 下载 |
| --- | --- | --- | --- |
| Windows | x64 | 安装包 | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Setup-2.0.0-win-x64.exe) |
| Windows | x64 | 便携版 EXE | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Portable-2.0.0-win-x64.exe) |
| Windows | arm64 | 安装包 | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Setup-2.0.0-win-arm64.exe) |
| Windows | arm64 | 便携版 EXE | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-Portable-2.0.0-win-arm64.exe) |
| macOS | Intel x64 | DMG | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-2.0.0-mac-x64.dmg) |
| macOS | Apple Silicon arm64 | DMG | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-2.0.0-mac-arm64.dmg) |
| Linux | x64 | AppImage | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-2.0.0-linux-x64.AppImage) |
| Linux | x64 | deb | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-2.0.0-linux-x64.deb) |
| Linux | arm64 | AppImage | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-2.0.0-linux-arm64.AppImage) |
| Linux | arm64 | deb | [下载](https://github.com/gmkrxb/codex-history-sync/releases/latest/download/Codex-History-Sync-2.0.0-linux-arm64.deb) |

Release 产物由 GitHub Actions 在对应系统和架构上自动构建。

## 快速开始

安装依赖并启动开发版：

```powershell
git clone https://github.com/gmkrxb/codex-history-sync.git
cd codex-history-sync
npm install
npm run electron:dev
```

如果只想构建前端静态资源：

```powershell
npm run build
```

请在仓库根目录执行命令。

## 命令总览

### npm 脚本

| 命令 | 作用 |
| --- | --- |
| `npm run dev` | 只启动 Vite 前端开发服务，默认地址为 `http://localhost:5173/`。 |
| `npm run build` | 构建 Vue 前端资源，输出到 `dist/`。 |
| `npm run electron:dev` | 同时启动 Vite 和 Electron，适合本地开发调试。 |
| `npm run electron:build` | 构建前端并按当前系统执行 Electron 打包。 |
| `npm run electron:build:win` | 构建 Windows 安装包和便携版 exe。 |
| `npm run electron:build:mac` | 构建 macOS DMG，仅建议在 macOS 上执行。 |
| `npm run electron:build:linux` | 构建 Linux AppImage/deb，仅建议在 Linux 上执行。 |

### 后端可执行文件

发布版 Electron 不直接依赖本机 Python，而是把 Python 后端打包成可执行文件放入 `backend/`：

Windows：

```powershell
python -m PyInstaller --onefile --clean --noconfirm --name sync_backend --distpath backend --workpath backend\build --specpath backend backend\sync_backend.py
```

macOS / Linux：

```bash
python3 -m PyInstaller --onefile --clean --noconfirm --name sync_backend --distpath backend --workpath backend/build --specpath backend backend/sync_backend.py
```

打包产物会是：

- Windows: `backend/sync_backend.exe`
- macOS / Linux: `backend/sync_backend`

## 后端 CLI 详细参数

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
| `--json` | 以 JSON 输出结果，Electron 调用和脚本集成建议使用。 |
| `--codex-home <path>` | 指定 Codex 数据目录；默认使用当前用户的 `~/.codex`。 |

### 命令

| 命令 | 参数 | 说明 |
| --- | --- | --- |
| `status` | 无 | 读取当前 provider、模型、线程数量、provider 分布、备份列表等状态。 |
| `detect` | 无 | 检测当前系统、Codex home、配置文件、认证文件和数据库路径。 |
| `processes` | 无 | 检测 Codex 或辅助进程是否仍在运行。 |
| `close-processes` | 无 | 尝试一键关闭检测到的 Codex 相关进程；失败时返回手动命令。 |
| `sync` | 无 | 同步 SQLite 和 JSONL 中的 provider 到当前 provider；执行前会检测 Codex 进程并创建备份。 |
| `backup` | 无 | 手动创建一份 SQLite 备份。 |
| `restore` | `--backup <path>` 可选 | 从指定备份恢复；不传 `--backup` 时使用最新备份。恢复前会再创建安全备份。 |
| `backup-detail` | `--backup <path>` 必填 | 查看指定备份的详情，包括线程数、provider 分布和线程预览。 |
| `delete-backup` | `--backup <path>` 必填 | 删除指定 SQLite 备份和配套 JSONL 元数据备份。 |

### 常用示例

查看状态：

```powershell
py -3 backend\sync_backend.py --json status
```

检测环境：

```powershell
py -3 backend\sync_backend.py --json detect
```

检测 Codex 进程：

```powershell
py -3 backend\sync_backend.py --json processes
```

尝试关闭 Codex 相关进程：

```powershell
py -3 backend\sync_backend.py --json close-processes
```

执行同步：

```powershell
py -3 backend\sync_backend.py --json sync
```

手动备份：

```powershell
py -3 backend\sync_backend.py --json backup
```

恢复最新备份：

```powershell
py -3 backend\sync_backend.py --json restore
```

恢复指定备份：

```powershell
py -3 backend\sync_backend.py --json restore --backup "C:\Users\you\.codex\history_sync_backups\state_5.sqlite.pre-sync.20260529-221500.bak"
```

查看备份详情：

```powershell
py -3 backend\sync_backend.py --json backup-detail --backup "C:\Users\you\.codex\history_sync_backups\state_5.sqlite.pre-sync.20260529-221500.bak"
```

删除备份：

```powershell
py -3 backend\sync_backend.py --json delete-backup --backup "C:\Users\you\.codex\history_sync_backups\state_5.sqlite.pre-sync.20260529-221500.bak"
```

指定 Codex 数据目录：

```powershell
py -3 backend\sync_backend.py --codex-home "D:\CodexData\.codex" --json status
```

## 安全说明

这个工具会修改本机 Codex 本地数据。它会自动创建备份，但同步或恢复前仍建议关闭 Codex Desktop。应用会在写入前检测 Codex 进程，如果检测到仍在运行，会阻止同步，并提供一键关闭和手动命令。

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
├── backend/                # SQLite 和 JSONL 同步后端
├── electron/               # Electron 主进程与 preload
├── src/                    # Vue 3 渲染进程应用
├── docs/
│   └── screenshots/        # README 截图
├── package.json            # 应用脚本和 electron-builder 配置
├── vite.config.js
├── README.md
├── README_EN.md
└── LICENSE
```

## License

MIT
