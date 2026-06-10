const { app, BrowserWindow, ipcMain, shell } = require('electron')
const path = require('path')
const fs = require('fs')
const os = require('os')
const { execFile, execFileSync } = require('child_process')

const isDev = !app.isPackaged
let pythonCommand = null
const repositoryUrl = 'https://github.com/gmkrxb/codex-history-sync'
const releasesUrl = `${repositoryUrl}/releases`
const latestReleaseApi = 'https://api.github.com/repos/gmkrxb/codex-history-sync/releases/latest'

function getBackendPath() {
  if (isDev) {
    return path.join(__dirname, '..', 'backend', 'sync_backend.py')
  }
  const executableName = process.platform === 'win32' ? 'sync_backend.exe' : 'sync_backend'
  return path.join(process.resourcesPath, 'backend', executableName)
}

function getPythonCommand() {
  if (pythonCommand) {
    return pythonCommand
  }

  const candidates = process.platform === 'win32'
    ? [
        { command: 'py', args: ['-3'] },
        { command: 'python', args: [] }
      ]
    : [
        { command: 'python3', args: [] },
        { command: 'python', args: [] }
      ]

  pythonCommand = candidates[0]
  for (const candidate of candidates) {
    try {
      execFileSync(
        candidate.command,
        [...candidate.args, '-c', 'import sys; raise SystemExit(sys.version_info < (3, 10))'],
        { stdio: 'ignore' }
      )
      pythonCommand = candidate
      break
    } catch {
      // Try the next common Python launcher name.
    }
  }
  return pythonCommand
}

function getBackendEnv() {
  return {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1'
  }
}

function getBackendCommand(args) {
  const backendPath = getBackendPath()
  if (isDev) {
    const python = getPythonCommand()
    return {
      command: python.command,
      args: [...python.args, backendPath, '--json', ...args]
    }
  }
  return {
    command: backendPath,
    args: ['--json', ...args]
  }
}

function parseBackendJson(stdout) {
  const json = JSON.parse(stdout.trim())
  if (!json.ok) {
    throw new Error(json.error || 'Unknown backend error')
  }
  return json
}

function callBackend(args) {
  return new Promise((resolve, reject) => {
    const backend = getBackendCommand(args)
    execFile(backend.command, backend.args, {
      timeout: 30000,
      encoding: 'utf-8',
      env: getBackendEnv(),
      maxBuffer: 10 * 1024 * 1024
    }, (error, stdout, stderr) => {
      if (error && !stdout) {
        reject(new Error(error.message || stderr || 'Backend execution failed'))
        return
      }
      try {
        resolve(parseBackendJson(stdout))
      } catch (e) {
        reject(new Error(`Backend JSON parse failed: ${e.message}\nOutput: ${stdout}`))
      }
    })
  })
}

function psQuote(value) {
  return `'${String(value).replace(/'/g, "''")}'`
}

function shQuote(value) {
  return `'${String(value).replace(/'/g, "'\"'\"'")}'`
}

function readElevatedResult(stdoutPath, stderrPath) {
  const stdout = fs.existsSync(stdoutPath) ? fs.readFileSync(stdoutPath, 'utf8') : ''
  const stderr = fs.existsSync(stderrPath) ? fs.readFileSync(stderrPath, 'utf8') : ''
  if (!stdout.trim()) {
    throw new Error(stderr.trim() || '管理员授权被取消，或提权命令没有返回结果')
  }
  try {
    return { ...parseBackendJson(stdout), elevated: true }
  } catch (e) {
    throw new Error(`提权执行返回异常: ${e.message}\n${stderr}`)
  }
}

function cleanupTempFiles(paths) {
  for (const item of paths) {
    try {
      if (item && fs.existsSync(item)) fs.unlinkSync(item)
    } catch {
      // Best-effort cleanup.
    }
  }
}

function callBackendElevated(args) {
  return new Promise((resolve, reject) => {
    const backend = getBackendCommand(args)
    const tempDir = app.getPath('temp') || os.tmpdir()
    const runId = `codex-history-sync-${Date.now()}-${Math.random().toString(36).slice(2)}`
    const stdoutPath = path.join(tempDir, `${runId}.stdout.json`)
    const stderrPath = path.join(tempDir, `${runId}.stderr.txt`)
    const exitPath = path.join(tempDir, `${runId}.exit.txt`)
    const scriptPath = path.join(tempDir, process.platform === 'win32' ? `${runId}.ps1` : `${runId}.sh`)

    const done = (error) => {
      try {
        const hasStdout = fs.existsSync(stdoutPath) && fs.readFileSync(stdoutPath, 'utf8').trim()
        if (error && !hasStdout) {
          const stderr = fs.existsSync(stderrPath) ? fs.readFileSync(stderrPath, 'utf8') : ''
          reject(new Error(stderr.trim() || error.message || '提权执行失败'))
          return
        }
        resolve(readElevatedResult(stdoutPath, stderrPath))
      } catch (e) {
        reject(e)
      } finally {
        cleanupTempFiles([stdoutPath, stderrPath, exitPath, scriptPath])
      }
    }

    if (process.platform === 'win32') {
      const commandLine = [backend.command, ...backend.args].map(psQuote).join(' ')
      const script = [
        '$ErrorActionPreference = "Stop"',
        '$env:PYTHONIOENCODING = "utf-8"',
        '$env:PYTHONUTF8 = "1"',
        'try {',
        `  & ${commandLine} 1> ${psQuote(stdoutPath)} 2> ${psQuote(stderrPath)}`,
        '  $code = $LASTEXITCODE',
        '} catch {',
        `  $_ | Out-File -Encoding utf8 ${psQuote(stderrPath)}`,
        '  $code = 1',
        '}',
        `Set-Content -Encoding utf8 -Path ${psQuote(exitPath)} -Value $code`,
        'exit $code'
      ].join('\n')
      fs.writeFileSync(scriptPath, script, 'utf8')
      const startCommand = [
        'Start-Process',
        '-FilePath',
        psQuote('powershell.exe'),
        '-ArgumentList',
        `@(${['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', scriptPath].map(psQuote).join(',')})`,
        '-Verb',
        'RunAs',
        '-Wait'
      ].join(' ')
      execFile('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', startCommand], {
        timeout: 120000,
        encoding: 'utf-8',
        env: getBackendEnv(),
        maxBuffer: 10 * 1024 * 1024
      }, done)
      return
    }

    const commandLine = [backend.command, ...backend.args].map(shQuote).join(' ')
    const script = [
      '#!/bin/sh',
      'export PYTHONIOENCODING=utf-8',
      'export PYTHONUTF8=1',
      `${commandLine} > ${shQuote(stdoutPath)} 2> ${shQuote(stderrPath)}`,
      'code=$?',
      `printf "%s" "$code" > ${shQuote(exitPath)}`,
      'exit "$code"'
    ].join('\n')
    fs.writeFileSync(scriptPath, script, { encoding: 'utf8', mode: 0o700 })

    if (process.platform === 'darwin') {
      const osaCommand = `do shell script ${JSON.stringify(`/bin/sh ${shQuote(scriptPath)}`)} with administrator privileges`
      execFile('osascript', ['-e', osaCommand], {
        timeout: 120000,
        encoding: 'utf-8',
        env: getBackendEnv(),
        maxBuffer: 10 * 1024 * 1024
      }, done)
      return
    }

    execFile('pkexec', ['/bin/sh', scriptPath], {
      timeout: 120000,
      encoding: 'utf-8',
      env: getBackendEnv(),
      maxBuffer: 10 * 1024 * 1024
    }, done)
  })
}

function normalizeVersion(value) {
  return String(value || '').trim().replace(/^v/i, '')
}

function compareVersions(left, right) {
  const a = normalizeVersion(left).split(/[.-]/).map(part => Number.parseInt(part, 10) || 0)
  const b = normalizeVersion(right).split(/[.-]/).map(part => Number.parseInt(part, 10) || 0)
  const length = Math.max(a.length, b.length)
  for (let i = 0; i < length; i += 1) {
    if ((a[i] || 0) > (b[i] || 0)) return 1
    if ((a[i] || 0) < (b[i] || 0)) return -1
  }
  return 0
}

async function checkForUpdates() {
  const currentVersion = app.getVersion()
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 7000)
  try {
    const response = await fetch(latestReleaseApi, {
      signal: controller.signal,
      headers: {
        Accept: 'application/vnd.github+json',
        'User-Agent': `Codex-History-Sync/${currentVersion}`
      }
    })
    if (!response.ok) {
      return {
        action: 'check-update',
        checked: false,
        currentVersion,
        repositoryUrl,
        releasesUrl,
        error: `GitHub returned HTTP ${response.status}`
      }
    }
    const release = await response.json()
    const latestVersion = normalizeVersion(release.tag_name || release.name)
    return {
      action: 'check-update',
      checked: true,
      currentVersion,
      latestVersion,
      hasUpdate: compareVersions(latestVersion, currentVersion) > 0,
      repositoryUrl,
      releasesUrl,
      releaseUrl: release.html_url || releasesUrl,
      releaseName: release.name || release.tag_name || '',
      publishedAt: release.published_at || null,
      body: release.body || '',
      assets: Array.isArray(release.assets)
        ? release.assets.map(asset => ({
            name: asset.name,
            size: asset.size,
            downloadUrl: asset.browser_download_url
          }))
        : []
    }
  } catch (e) {
    return {
      action: 'check-update',
      checked: false,
      currentVersion,
      repositoryUrl,
      releasesUrl,
      error: e.name === 'AbortError' ? 'Update check timed out' : e.message
    }
  } finally {
    clearTimeout(timer)
  }
}

let mainWindow = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 960,
    minHeight: 640,
    frame: false,
    backgroundColor: '#0f1923',
    icon: isDev
      ? path.join(__dirname, '..', 'assets', 'codex-sync-modern.ico')
      : path.join(process.resourcesPath, 'assets', 'codex-sync-modern.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }

  mainWindow.on('maximize', () => {
    mainWindow.webContents.send('window:maximized', true)
  })
  mainWindow.on('unmaximize', () => {
    mainWindow.webContents.send('window:maximized', false)
  })
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  app.quit()
})

// IPC handlers
ipcMain.handle('backend:status', () => callBackend(['status']))
ipcMain.handle('backend:detect', () => callBackend(['detect']))
ipcMain.handle('backend:diagnose', () => callBackend(['diagnose']))
ipcMain.handle('backend:preflight', () => callBackend(['preflight']))
ipcMain.handle('backend:processes', () => callBackend(['processes']))
ipcMain.handle('backend:closeProcesses', () => callBackend(['close-processes']))
ipcMain.handle('backend:sync', () => callBackend(['sync']))
ipcMain.handle('backend:syncElevated', () => callBackendElevated(['sync']))
ipcMain.handle('backend:repair', () => callBackend(['repair']))
ipcMain.handle('backend:repairElevated', () => callBackendElevated(['repair']))
ipcMain.handle('backend:backup', () => callBackend(['backup']))
ipcMain.handle('backend:restore', (_, backupPath) => {
  const args = ['restore']
  if (backupPath) args.push('--backup', backupPath)
  return callBackend(args)
})
ipcMain.handle('backend:restoreElevated', (_, backupPath) => {
  const args = ['restore']
  if (backupPath) args.push('--backup', backupPath)
  return callBackendElevated(args)
})
ipcMain.handle('backend:backupDetail', (_, backupPath) => callBackend(['backup-detail', '--backup', backupPath]))
ipcMain.handle('backend:deleteBackup', (_, backupPath) => callBackend(['delete-backup', '--backup', backupPath]))

ipcMain.handle('app:checkUpdate', () => checkForUpdates())
ipcMain.handle('open:external', (_, url) => {
  const target = String(url || '')
  if (!target.startsWith(repositoryUrl)) {
    throw new Error('Only project GitHub links can be opened from this action.')
  }
  return shell.openExternal(target)
})

ipcMain.handle('open:backupsDir', async () => {
  const status = await callBackend(['status'])
  shell.openPath(status.backup_dir)
})

ipcMain.handle('window:minimize', () => {
  if (mainWindow) {
    mainWindow.minimize()
  }
})
ipcMain.handle('window:maximize', () => {
  if (!mainWindow) return
  if (mainWindow.isMaximized()) {
    mainWindow.unmaximize()
  } else {
    mainWindow.maximize()
  }
})
ipcMain.handle('window:close', () => {
  if (mainWindow) {
    mainWindow.close()
  }
})
ipcMain.handle('window:isMaximized', () => mainWindow?.isMaximized() ?? false)
