const { app, BrowserWindow, ipcMain, shell } = require('electron')
const path = require('path')
const { execFile } = require('child_process')

const isDev = !app.isPackaged

function getBackendPath() {
  if (isDev) {
    return path.join(__dirname, '..', 'backend', 'sync_backend.py')
  }
  const executableName = process.platform === 'win32' ? 'sync_backend.exe' : 'sync_backend'
  return path.join(process.resourcesPath, 'backend', executableName)
}

function getPythonCommand() {
  return process.platform === 'win32'
    ? { command: 'py', args: ['-3'] }
    : { command: 'python3', args: [] }
}

function callBackend(args) {
  return new Promise((resolve, reject) => {
    const backendPath = getBackendPath()
    const backendEnv = {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1'
    }
    if (isDev) {
      const python = getPythonCommand()
      execFile(python.command, [...python.args, backendPath, '--json', ...args], {
        timeout: 30000,
        encoding: 'utf-8',
        env: backendEnv,
        maxBuffer: 10 * 1024 * 1024
      }, (error, stdout, stderr) => {
        if (error && !stdout) {
          reject(new Error(error.message || stderr || 'Backend execution failed'))
          return
        }
        try {
          const json = JSON.parse(stdout.trim())
          if (!json.ok) {
            reject(new Error(json.error || 'Unknown backend error'))
            return
          }
          resolve(json)
        } catch (e) {
          reject(new Error(`Backend JSON parse failed: ${e.message}\nOutput: ${stdout}`))
        }
      })
    } else {
      execFile(backendPath, ['--json', ...args], {
        timeout: 30000,
        encoding: 'utf-8',
        env: backendEnv,
        maxBuffer: 10 * 1024 * 1024
      }, (error, stdout, stderr) => {
        if (error && !stdout) {
          reject(new Error(error.message || stderr || 'Backend execution failed'))
          return
        }
        try {
          const json = JSON.parse(stdout.trim())
          if (!json.ok) {
            reject(new Error(json.error || 'Unknown backend error'))
            return
          }
          resolve(json)
        } catch (e) {
          reject(new Error(`Backend JSON parse failed: ${e.message}\nOutput: ${stdout}`))
        }
      })
    }
  })
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
ipcMain.handle('backend:processes', () => callBackend(['processes']))
ipcMain.handle('backend:closeProcesses', () => callBackend(['close-processes']))
ipcMain.handle('backend:sync', () => callBackend(['sync']))
ipcMain.handle('backend:backup', () => callBackend(['backup']))
ipcMain.handle('backend:restore', (_, backupPath) => {
  const args = ['restore']
  if (backupPath) args.push('--backup', backupPath)
  return callBackend(args)
})
ipcMain.handle('backend:backupDetail', (_, backupPath) => callBackend(['backup-detail', '--backup', backupPath]))
ipcMain.handle('backend:deleteBackup', (_, backupPath) => callBackend(['delete-backup', '--backup', backupPath]))

ipcMain.handle('open:backupsDir', async () => {
  const status = await callBackend(['status'])
  shell.openPath(status.backup_dir)
})

ipcMain.handle('window:minimize', () => mainWindow?.minimize())
ipcMain.handle('window:maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize()
  } else {
    mainWindow?.maximize()
  }
})
ipcMain.handle('window:close', () => mainWindow?.close())
ipcMain.handle('window:isMaximized', () => mainWindow?.isMaximized() ?? false)
