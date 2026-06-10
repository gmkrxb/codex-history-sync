const api = window.codexAPI

export async function getStatus() {
  return api.getStatus()
}

export async function detectEnvironment() {
  return api.detect()
}

export async function diagnoseDatabase() {
  return api.diagnose()
}

export async function preflightSync() {
  return api.preflight()
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

export async function syncProvidersElevated() {
  return api.syncElevated()
}

export async function repairDatabase() {
  return api.repair()
}

export async function repairDatabaseElevated() {
  return api.repairElevated()
}

export async function createBackup() {
  return api.backup()
}

export async function restoreBackup(backupPath) {
  return api.restore(backupPath)
}

export async function restoreBackupElevated(backupPath) {
  return api.restoreElevated(backupPath)
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

export async function checkUpdate() {
  return api.checkUpdate()
}

export async function openExternal(url) {
  return api.openExternal(url)
}

export function onMaximizedChange(callback) {
  if (window.codexAPI?.onMaximized) {
    window.codexAPI.onMaximized(callback)
  }
}
