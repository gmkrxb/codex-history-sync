const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('codexAPI', {
  getStatus: () => ipcRenderer.invoke('backend:status'),
  detect: () => ipcRenderer.invoke('backend:detect'),
  checkProcesses: () => ipcRenderer.invoke('backend:processes'),
  closeProcesses: () => ipcRenderer.invoke('backend:closeProcesses'),
  sync: () => ipcRenderer.invoke('backend:sync'),
  backup: () => ipcRenderer.invoke('backend:backup'),
  restore: (backupPath) => ipcRenderer.invoke('backend:restore', backupPath),
  getBackupDetail: (backupPath) => ipcRenderer.invoke('backend:backupDetail', backupPath),
  deleteBackup: (backupPath) => ipcRenderer.invoke('backend:deleteBackup', backupPath),
  openBackupsDir: () => ipcRenderer.invoke('open:backupsDir'),
  minimize: () => ipcRenderer.invoke('window:minimize'),
  maximize: () => ipcRenderer.invoke('window:maximize'),
  close: () => ipcRenderer.invoke('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:isMaximized'),
  onMaximized: (callback) => {
    ipcRenderer.on('window:maximized', (_, val) => callback(val))
  }
})
