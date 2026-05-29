<template>
  <div class="view">
    <div class="view-header">
      <div>
        <h2 class="view-title">备份恢复</h2>
        <p class="view-desc">管理 SQLite 备份和 JSONL 元数据备份，可查看详情、恢复或删除。</p>
      </div>
      <div class="header-actions">
        <button class="btn btn-secondary" @click="doBackup">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          手动备份
        </button>
        <button class="btn btn-secondary" @click="openDir">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          打开目录
        </button>
      </div>
    </div>

    <div class="card" v-if="status">
      <div class="backup-info">
        <div class="backup-stat">
          <span class="backup-stat-value">{{ status.backups?.length || 0 }}</span>
          <span class="backup-stat-label">份备份</span>
        </div>
        <div class="backup-stat">
          <span class="backup-stat-value">{{ status.total_threads }}</span>
          <span class="backup-stat-label">条线程</span>
        </div>
        <div class="backup-path">
          <span class="path-label">备份目录</span>
          <span class="path-value">{{ status.backup_dir }}</span>
        </div>
      </div>
    </div>

    <div class="card">
      <h3 class="card-title">备份列表</h3>
      <p class="card-desc" v-if="status?.backups?.length">
        最近一份备份时间 {{ status.backups[0]?.modified_at }}
      </p>
      <p class="card-desc" v-else>还没有发现任何备份文件。</p>

      <div class="backup-list" v-if="status?.backups?.length">
        <div
          v-for="(backup, index) in status.backups"
          :key="backup.path"
          class="backup-item"
          :class="{ selected: selectedIndex === index }"
          @click="selectedIndex = index"
        >
          <div class="backup-item-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <div class="backup-item-info">
            <div class="backup-item-name">{{ backup.name }}</div>
            <div class="backup-item-time">
              {{ backup.modified_at }} · {{ formatBytes(backup.size_bytes) }}
              <span v-if="backup.session_meta_backup_path"> · 含 JSONL 元数据</span>
            </div>
          </div>
          <div class="backup-item-actions">
            <button class="btn btn-sm btn-secondary" @click.stop="openDetail(backup)">详情</button>
            <button class="btn btn-sm btn-warning" @click.stop="doRestore(backup)">恢复</button>
          </div>
        </div>
      </div>
      <div class="empty-state" v-else>
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        <p>暂无备份文件</p>
      </div>
    </div>

    <Teleport to="body">
      <Transition name="modal">
        <div class="modal-overlay" v-if="showDetail" @click.self="showDetail = false">
          <div class="modal-card modal-card-wide modal-card-tall">
            <div class="modal-header-fixed">
              <h3>备份详情</h3>
            </div>

            <div class="modal-scroll-body">
              <p v-if="detailLoading">正在读取备份...</p>
              <template v-else-if="backupDetail">
                <div class="detail-grid">
                  <div>
                    <span class="detail-label">文件名</span>
                    <strong>{{ backupDetail.name }}</strong>
                  </div>
                  <div>
                    <span class="detail-label">大小</span>
                    <strong>{{ formatBytes(backupDetail.size_bytes) }}</strong>
                  </div>
                  <div>
                    <span class="detail-label">线程数</span>
                    <strong>{{ backupDetail.total_threads }}</strong>
                  </div>
                  <div>
                    <span class="detail-label">JSONL 元数据</span>
                    <strong>{{ backupDetail.session_meta_files }} 文件 / {{ backupDetail.session_meta_lines }} 条</strong>
                  </div>
                </div>

                <div class="detail-section">
                  <h4>Provider 分布</h4>
                  <div class="provider-pills">
                    <span v-for="row in backupDetail.provider_counts" :key="row.provider" class="provider-pill">
                      {{ row.provider }} · {{ row.count }}
                    </span>
                  </div>
                </div>

                <div class="detail-section">
                  <h4>备份内线程预览</h4>
                  <div class="detail-thread-list">
                    <div class="detail-thread" v-for="thread in backupDetail.threads" :key="thread.id">
                      <span class="detail-thread-title">{{ thread.title || thread.id }}</span>
                      <span class="detail-thread-meta">{{ thread.model_provider }} · {{ thread.model || 'unknown model' }}</span>
                    </div>
                  </div>
                </div>

                <div class="detail-path">{{ backupDetail.path }}</div>
              </template>
            </div>

            <div class="modal-actions modal-actions-fixed">
              <button class="btn btn-secondary" @click="showDetail = false">关闭</button>
              <button class="btn btn-danger" @click="requestDeleteFromDetail" :disabled="!backupDetail">删除备份</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Teleport to="body">
      <Transition name="modal">
        <div class="modal-overlay" v-if="showConfirm" @click.self="showConfirm = false">
          <div class="modal-card">
            <div class="modal-icon modal-icon-warn">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            </div>
            <h3>确认恢复</h3>
            <p>将恢复这个备份:</p>
            <div class="modal-highlight modal-highlight-sm">{{ restoreTarget?.name }}</div>
            <p class="modal-note">恢复前会再自动生成一份安全备份。请先关闭 Codex。</p>
            <div class="modal-actions">
              <button class="btn btn-secondary" @click="showConfirm = false">取消</button>
              <button class="btn btn-warning" @click="confirmRestore">确认恢复</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Teleport to="body">
      <Transition name="modal">
        <div class="modal-overlay" v-if="showDeleteConfirm" @click.self="showDeleteConfirm = false">
          <div class="modal-card">
            <div class="modal-icon modal-icon-danger">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
            </div>
            <h3>删除备份</h3>
            <p>这个操作会删除 SQLite 备份，以及配套的 JSONL 元数据备份。</p>
            <div class="modal-highlight modal-highlight-sm">{{ deleteTarget?.name }}</div>
            <p class="modal-note">删除后无法从这个备份恢复。</p>
            <div class="modal-actions">
              <button class="btn btn-secondary" @click="showDeleteConfirm = false">取消</button>
              <button class="btn btn-danger" @click="confirmDelete">确认删除</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { inject, ref } from 'vue'
import { createBackup, deleteBackup, getBackupDetail, openBackupsDir, restoreBackup } from '../api.js'

defineProps({
  status: Object,
  logs: Array
})
const emit = defineEmits(['refresh', 'log'])

const addLog = inject('addLog')
const showToast = inject('showToast')
const selectedIndex = ref(-1)
const showConfirm = ref(false)
const showDetail = ref(false)
const showDeleteConfirm = ref(false)
const detailLoading = ref(false)
const restoreTarget = ref(null)
const deleteTarget = ref(null)
const backupDetail = ref(null)

function formatBytes(value) {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let unit = 0
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024
    unit += 1
  }
  return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}

async function doBackup() {
  try {
    const result = await createBackup()
    addLog(`手动备份完成: ${result.backup_path}`)
    showToast('手动备份完成', 'success')
    emit('refresh')
  } catch (e) {
    addLog(`备份失败: ${e.message}`)
    showToast(`备份失败: ${e.message}`, 'error')
  }
}

async function openDir() {
  try {
    await openBackupsDir()
    addLog('已打开备份目录')
  } catch (e) {
    addLog(`打开目录失败: ${e.message}`)
    showToast(`打开目录失败: ${e.message}`, 'error')
  }
}

async function openDetail(backup) {
  showDetail.value = true
  backupDetail.value = null
  detailLoading.value = true
  try {
    backupDetail.value = await getBackupDetail(backup.path)
  } catch (e) {
    addLog(`读取备份详情失败: ${e.message}`)
    showToast(`读取备份详情失败: ${e.message}`, 'error')
    showDetail.value = false
  } finally {
    detailLoading.value = false
  }
}

function doRestore(backup) {
  restoreTarget.value = backup
  showConfirm.value = true
}

async function confirmRestore() {
  showConfirm.value = false
  try {
    const result = await restoreBackup(restoreTarget.value.path)
    addLog(`恢复完成。来源备份: ${result.restored_from}`)
    addLog(`恢复前安全备份: ${result.safety_backup}`)
    showToast('恢复完成，建议重新打开 Codex', 'success')
    emit('refresh')
  } catch (e) {
    addLog(`恢复失败: ${e.message}`)
    showToast(`恢复失败: ${e.message}`, 'error')
  }
}

function requestDeleteFromDetail() {
  deleteTarget.value = backupDetail.value
  showDeleteConfirm.value = true
}

async function confirmDelete() {
  showDeleteConfirm.value = false
  try {
    const result = await deleteBackup(deleteTarget.value.path)
    addLog(`已删除备份: ${result.deleted.join(', ')}`)
    showToast('备份已删除', 'success')
    showDetail.value = false
    backupDetail.value = null
    emit('refresh')
  } catch (e) {
    addLog(`删除备份失败: ${e.message}`)
    showToast(`删除备份失败: ${e.message}`, 'error')
  }
}
</script>
