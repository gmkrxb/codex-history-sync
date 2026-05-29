<template>
  <div class="view">
    <div class="view-header">
      <div>
        <h2 class="view-title">历史同步</h2>
        <p class="view-desc">把旧 provider 下的本地历史归并到当前正在使用的 provider。</p>
      </div>
      <div class="header-actions">
        <button class="btn btn-primary" @click="doSync" :disabled="syncing || checkingProcesses || closingProcesses">
          <svg v-if="!syncing && !checkingProcesses && !closingProcesses" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          <span v-if="syncing || checkingProcesses || closingProcesses" class="spinner"></span>
          {{ syncButtonText }}
        </button>
      </div>
    </div>

    <div class="card" v-if="status">
      <div class="sync-status-grid">
        <div class="sync-info-block">
          <div class="sync-label">当前 Provider</div>
          <div class="sync-big-value">{{ status.current_provider }}</div>
          <div class="sync-sub">来源: {{ status.current_provider_source || '未知' }}</div>
        </div>
        <div class="sync-arrow">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </div>
        <div class="sync-info-block">
          <div class="sync-label">待同步记录</div>
          <div class="sync-big-value" :class="pendingTotal > 0 ? 'text-warn' : 'text-ok'">
            {{ pendingTotal }}
          </div>
          <div class="sync-sub">
            DB {{ status.movable_threads || 0 }} / JSONL {{ status.mismatched_session_meta || 0 }}
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <h3 class="card-title">同步说明</h3>
      <div class="explain-list">
        <div class="explain-item">
          <div class="explain-num">1</div>
          <div class="explain-text">
            <strong>自动检测环境</strong>
            <p>自动识别 Windows/macOS 下的 <code>~/.codex</code>、配置文件和 SQLite 数据库。</p>
          </div>
        </div>
        <div class="explain-item">
          <div class="explain-num">2</div>
          <div class="explain-text">
            <strong>先确认 Codex 已关闭</strong>
            <p>同步前会检测 Codex 进程，只有确认关闭后才允许写入数据库和会话文件。</p>
          </div>
        </div>
        <div class="explain-item">
          <div class="explain-num">3</div>
          <div class="explain-text">
            <strong>同时修复索引和原始会话</strong>
            <p>除了更新 <code>state_5.sqlite</code>，也会同步 JSONL 里的 <code>session_meta.model_provider</code>。</p>
          </div>
        </div>
        <div class="explain-item">
          <div class="explain-num">4</div>
          <div class="explain-text">
            <strong>写入后再次校验</strong>
            <p>如果校验发现仍有旧 provider，后端会报错，不再给出假成功。</p>
          </div>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <Transition name="modal">
        <div class="modal-overlay" v-if="showProcessBlocker" @click.self="showProcessBlocker = false">
          <div class="modal-card modal-card-wide">
            <div class="modal-icon modal-icon-warn">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            </div>
            <h3>请先关闭 Codex</h3>
            <p>检测到 Codex 或它的辅助进程仍在运行。为了避免 SQLite/WAL 被占用或索引被重新写回，请关闭后再同步。</p>

            <div class="process-list" v-if="processState?.processes?.length">
              <div class="process-item" v-for="item in processState.processes" :key="`${item.pid}-${item.name}`">
                <div>
                  <span>{{ item.name || 'Codex' }}</span>
                  <span class="process-kind" v-if="item.kind === 'helper'">辅助进程</span>
                </div>
                <span class="process-pid">PID {{ item.pid }}</span>
              </div>
            </div>

            <div class="manual-command-box" v-if="processState?.manual_commands?.length">
              <div class="manual-command-title">一键关闭失败时，可复制到 {{ processState.platform === 'macos' ? 'Terminal' : '管理员 PowerShell / CMD' }} 执行</div>
              <code v-for="command in processState.manual_commands" :key="command">{{ command }}</code>
            </div>

            <div class="modal-actions">
              <button class="btn btn-secondary" @click="showProcessBlocker = false">取消</button>
              <button class="btn btn-warning" @click="closeProcesses" :disabled="closingProcesses">
                <span v-if="closingProcesses" class="spinner"></span>
                一键关闭
              </button>
              <button class="btn btn-primary" @click="recheckProcesses" :disabled="checkingProcesses">
                <span v-if="checkingProcesses" class="spinner"></span>
                再次检测
              </button>
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
            <h3>确认同步</h3>
            <p>将把旧 provider 的记录统一归到当前 provider:</p>
            <div class="modal-highlight">{{ status?.current_provider }}</div>
            <p>预计更新 DB <strong>{{ status?.movable_threads || 0 }}</strong> 条，JSONL 元数据 <strong>{{ status?.mismatched_session_meta || 0 }}</strong> 条。</p>
            <p class="modal-note">同步前会自动创建 SQLite 备份和 JSONL 元数据备份。</p>
            <div class="modal-actions">
              <button class="btn btn-secondary" @click="showConfirm = false">取消</button>
              <button class="btn btn-primary" @click="confirmSync">确认同步</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Teleport to="body">
      <Transition name="modal">
        <div class="modal-overlay" v-if="showResult" @click.self="showResult = false">
          <div class="modal-card">
            <div class="modal-icon modal-icon-ok">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            </div>
            <h3>同步完成</h3>
            <p v-if="syncResult">已更新 DB <strong>{{ syncResult.updated_rows }}</strong> 条，JSONL 元数据 <strong>{{ syncResult.updated_session_meta }}</strong> 条。</p>
            <p class="modal-note">现在重新打开 Codex，历史列表应该会按当前 provider 重新显示。</p>
            <div class="modal-actions">
              <button class="btn btn-primary" @click="showResult = false">好的</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import { checkCodexProcesses, closeCodexProcesses, syncProviders } from '../api.js'

const props = defineProps({
  status: Object,
  logs: Array
})
const emit = defineEmits(['refresh', 'log'])

const addLog = inject('addLog')
const showToast = inject('showToast')
const checkingProcesses = ref(false)
const closingProcesses = ref(false)
const syncing = ref(false)
const showConfirm = ref(false)
const showProcessBlocker = ref(false)
const showResult = ref(false)
const syncResult = ref(null)
const processState = ref(null)

const pendingTotal = computed(() => {
  return (props.status?.movable_threads || 0) + (props.status?.mismatched_session_meta || 0)
})

const syncButtonText = computed(() => {
  if (syncing.value) return '同步中...'
  if (closingProcesses.value) return '关闭中...'
  if (checkingProcesses.value) return '检测中...'
  return '立即同步'
})

async function verifyCodexClosed() {
  checkingProcesses.value = true
  try {
    const result = await checkCodexProcesses()
    processState.value = result
    if (result.running) {
      showProcessBlocker.value = true
      addLog(`检测到 Codex 仍在运行: ${result.processes.map(item => `${item.name}(${item.pid})`).join(', ')}`)
      return false
    }
    addLog('Codex 进程检测通过，可以同步。')
    return true
  } catch (e) {
    addLog(`进程检测失败: ${e.message}`)
    showToast(`进程检测失败: ${e.message}`, 'error')
    return false
  } finally {
    checkingProcesses.value = false
  }
}

async function doSync() {
  if (!props.status) {
    emit('refresh')
    return
  }
  if (pendingTotal.value <= 0) {
    addLog('同步跳过：没有需要迁移的记录。')
    showToast('没有需要迁移的记录', 'info')
    return
  }
  if (await verifyCodexClosed()) {
    showConfirm.value = true
  }
}

async function closeProcesses() {
  closingProcesses.value = true
  try {
    const result = await closeCodexProcesses()
    processState.value = result
    addLog(`一键关闭完成：已关闭 ${result.closed?.length || 0} 个进程，失败 ${result.failed?.length || 0} 个。`)
    if (result.running) {
      showToast('仍有进程未关闭，请使用下方命令手动关闭', 'error')
      return
    }
    showToast('Codex 已关闭，可以同步', 'success')
    showProcessBlocker.value = false
    showConfirm.value = true
  } catch (e) {
    addLog(`一键关闭失败: ${e.message}`)
    showToast(`一键关闭失败: ${e.message}`, 'error')
  } finally {
    closingProcesses.value = false
  }
}

async function recheckProcesses() {
  if (await verifyCodexClosed()) {
    showProcessBlocker.value = false
    showConfirm.value = true
  }
}

async function confirmSync() {
  showConfirm.value = false
  syncing.value = true
  try {
    const result = await syncProviders()
    syncResult.value = result
    showResult.value = true
    addLog(`同步完成。DB ${result.updated_rows} 条，JSONL ${result.updated_session_meta} 条。`)
    addLog(`SQLite 备份: ${result.backup_path}`)
    addLog(`JSONL 元数据备份: ${result.session_meta_backup_path}`)
    showToast('同步完成', 'success')
    emit('refresh')
  } catch (e) {
    addLog(`同步失败: ${e.message}`)
    showToast(`同步失败: ${e.message}`, 'error')
  } finally {
    syncing.value = false
  }
}
</script>
