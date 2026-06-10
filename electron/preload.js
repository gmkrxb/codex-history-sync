const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('codexAPI', {
  getStatus: () => ipcRenderer.invoke('backend:status'),
  detect: () => ipcRenderer.invoke('backend:detect'),
  diagnose: () => ipcRenderer.invoke('backend:diagnose'),
  preflight: () => ipcRenderer.invoke('backend:preflight'),
  checkProcesses: () => ipcRenderer.invoke('backend:processes'),
  closeProcesses: () => ipcRenderer.invoke('backend:closeProcesses'),
  sync: () => ipcRenderer.invoke('backend:sync'),
  syncElevated: () => ipcRenderer.invoke('backend:syncElevated'),
  repair: () => ipcRenderer.invoke('backend:repair'),
  repairElevated: () => ipcRenderer.invoke('backend:repairElevated'),
  backup: () => ipcRenderer.invoke('backend:backup'),
  restore: (backupPath) => ipcRenderer.invoke('backend:restore', backupPath),
  restoreElevated: (backupPath) => ipcRenderer.invoke('backend:restoreElevated', backupPath),
  getBackupDetail: (backupPath) => ipcRenderer.invoke('backend:backupDetail', backupPath),
  deleteBackup: (backupPath) => ipcRenderer.invoke('backend:deleteBackup', backupPath),
  checkUpdate: () => ipcRenderer.invoke('app:checkUpdate'),
  openExternal: (url) => ipcRenderer.invoke('open:external', url),
  openBackupsDir: () => ipcRenderer.invoke('open:backupsDir'),
  minimize: () => ipcRenderer.invoke('window:minimize'),
  maximize: () => ipcRenderer.invoke('window:maximize'),
  close: () => ipcRenderer.invoke('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:isMaximized'),
  onMaximized: (callback) => {
    ipcRenderer.on('window:maximized', (_, val) => callback(val))
  }
})
