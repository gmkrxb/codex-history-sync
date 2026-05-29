const api = window.codexAPI

export async function getStatus() {
  return api.getStatus()
}

export async function detectEnvironment() {
  return api.detect()
}

export async function checkCodexProcesses() {
  return api.checkProcesses()
}

export async function closeCodexProcesses() {
  return api.closeProcesses()
}

export async function syncProviders() {
  return api.sync()
}

export async function createBackup() {
  return api.backup()
}

export async function restoreBackup(backupPath) {
  return api.restore(backupPath)
}

export async function getBackupDetail(backupPath) {
  return api.getBackupDetail(backupPath)
}

export async function deleteBackup(backupPath) {
  return api.deleteBackup(backupPath)
}

export async function openBackupsDir() {
  return api.openBackupsDir()
}

export function onMaximizedChange(callback) {
  const { ipcRenderer } = window.require ? window.require('electron') : {}
  // Use the exposed API if available
  if (window.electronAPI?.onMaximized) {
    window.electronAPI.onMaximized(callback)
  }
}
