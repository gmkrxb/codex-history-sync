<template>
  <div class="view">
    <div class="view-header">
      <div>
        <h2 class="view-title">概览</h2>
        <p class="view-desc">管理本地历史同步、备份恢复与数据库健康状态。</p>
      </div>
      <div class="header-actions">
        <span class="badge" :class="pendingTotal > 0 ? 'badge-warning' : 'badge-success'">
          {{ pendingTotal > 0 ? `待同步 ${pendingTotal} 条` : '状态正常' }}
        </span>
        <button class="btn btn-secondary" @click="$emit('refresh')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          刷新状态
        </button>
      </div>
    </div>

    <div class="card hero-card">
      <div class="hero-content">
        <div class="hero-info">
          <h3>同步前概览</h3>
          <p class="hero-summary" v-if="status">
            共找到 <strong>{{ status.total_threads }}</strong> 条本地线程记录，
            当前有 <strong>{{ status.backups?.length || 0 }}</strong> 份可恢复备份。
          </p>
          <p class="hero-summary" v-else>正在读取本地状态...</p>
          <div class="hero-path" v-if="status">
            <span class="path-label">数据库路径</span>
            <span class="path-value">{{ status.db_path }}</span>
          </div>
        </div>
        <div class="hero-warning" v-if="pendingTotal > 0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <span>建议先关闭 Codex Desktop，再执行同步、修复或恢复</span>
        </div>
      </div>
    </div>

    <div class="metric-grid">
      <div class="card metric-card metric-accent">
        <div class="metric-label">当前 Provider</div>
        <div class="metric-value">{{ status?.current_provider || '--' }}</div>
        <div class="metric-meta">来源: {{ status?.current_provider_source || '未知' }}</div>
      </div>
      <div class="card metric-card">
        <div class="metric-label">当前模型</div>
        <div class="metric-value">{{ status?.current_model || '未读取到' }}</div>
        <div class="metric-meta">认证方式: {{ status?.auth_mode || '未读取到' }}</div>
      </div>
      <div class="card metric-card" :class="pendingTotal > 0 ? 'metric-warn' : 'metric-ok'">
        <div class="metric-label">待同步总数</div>
        <div class="metric-value">{{ status ? pendingTotal : '--' }}</div>
        <div class="metric-meta">DB {{ status?.movable_threads || 0 }} / JSONL {{ status?.mismatched_session_meta || 0 }}</div>
      </div>
      <div class="card metric-card">
        <div class="metric-label">线程总数</div>
        <div class="metric-value">{{ status?.total_threads ?? '--' }}</div>
        <div class="metric-meta">共发现 {{ status?.provider_counts?.length || 0 }} 个 provider</div>
        <div class="metric-hint">可用备份 {{ status?.backups?.length || 0 }} 份</div>
      </div>
    </div>

    <div class="card repair-card">
      <div class="repair-card-head">
        <div>
          <h3 class="card-title">数据库体检与修复</h3>
          <p class="card-desc">检测 SQLite 完整性、缺失的 threads 索引、空标题/预览、JSONL 元数据和 provider 不一致问题。</p>
        </div>
        <div class="header-actions">
          <button class="btn btn-secondary" @click="runDiagnosis" :disabled="repairBusy">
            <span v-if="diagnosing" class="spinner"></span>
            诊断数据库
          </button>
          <button class="btn btn-warning" @click="runRepair(false)" :disabled="repairBusy">
            <span v-if="repairing" class="spinner"></span>
            修复数据库
          </button>
        </div>
      </div>

      <div class="action-alert" v-if="repairError">
        <div>
          <h4>修复失败，可尝试提权重试</h4>
          <p>{{ repairError }}</p>
        </div>
        <button class="btn btn-warning" @click="runRepair(true)" :disabled="repairBusy">
          <span v-if="elevatedRepairing" class="spinner"></span>
          获取管理员权限后重试修复
        </button>
      </div>

      <div class="diagnosis-grid" v-if="diagnosis">
        <div>
          <span class="detail-label">SQLite 自检</span>
          <strong :class="diagnosis.quick_check === 'ok' ? 'text-ok' : 'text-warn'">{{ diagnosis.quick_check || '未完成' }}</strong>
        </div>
        <div>
          <span class="detail-label">扫描 JSONL</span>
          <strong>{{ diagnosis.session_files_found }} 个文件 / {{ diagnosis.recoverable_sessions }} 个会话</strong>
        </div>
        <div>
          <span class="detail-label">缺失索引</span>
          <strong>{{ diagnosis.missing_thread_records }} 条</strong>
        </div>
        <div>
          <span class="detail-label">空标题/预览</span>
          <strong>{{ diagnosis.empty_text_records }} 条</strong>
        </div>
        <div>
          <span class="detail-label">Provider 待修正</span>
          <strong>{{ diagnosis.provider_rows_to_sync }} 条 DB 记录</strong>
        </div>
        <div>
          <span class="detail-label">JSONL 待修正</span>
          <strong>{{ diagnosis.session_meta_status?.mismatched_session_meta || 0 }} 条元数据</strong>
        </div>
      </div>

      <div class="manual-command-box" v-if="diagnosis?.recommendations?.length">
        <div class="manual-command-title">建议</div>
        <code v-for="item in diagnosis.recommendations" :key="item">{{ item }}</code>
      </div>

      <div class="repair-result" v-if="repairResult">
        <h4>修复完成</h4>
        <p>
          重建索引 {{ repairResult.inserted_threads }} 条，
          补全文案 {{ repairResult.updated_text_threads }} 条，
          修正 provider {{ repairResult.normalized_provider_rows }} 条，
          更新 JSONL 元数据 {{ repairResult.updated_session_meta }} 条。
        </p>
        <p class="modal-note">安全备份: {{ repairResult.backup_path }}</p>
      </div>
    </div>

    <div class="card">
      <h3 class="card-title">Provider 统计</h3>
      <p class="card-desc" v-if="status?.provider_counts?.length">当前 provider 已高亮标记，方便确认同步目标。</p>
      <p class="card-desc" v-else>还没有读取到 provider 统计。</p>
      <table class="data-table" v-if="status?.provider_counts?.length">
        <thead>
          <tr>
            <th>Provider</th>
            <th class="col-num">线程数</th>
            <th class="col-flag">当前</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in status.provider_counts"
            :key="row.provider"
            :class="{ 'row-current': row.provider === status.current_provider }"
          >
            <td>{{ row.provider }}</td>
            <td class="col-num">{{ row.count }}</td>
            <td class="col-flag">
              <span v-if="row.provider === status.current_provider" class="check-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import { diagnoseDatabase, repairDatabase, repairDatabaseElevated } from '../api.js'

const props = defineProps({
  status: Object,
  logs: Array
})
const emit = defineEmits(['refresh', 'log'])

const addLog = inject('addLog')
const showToast = inject('showToast')
const diagnosis = ref(null)
const repairResult = ref(null)
const repairError = ref('')
const diagnosing = ref(false)
const repairing = ref(false)
const elevatedRepairing = ref(false)

const pendingTotal = computed(() => {
  return (props.status?.movable_threads || 0) + (props.status?.mismatched_session_meta || 0)
})

const repairBusy = computed(() => diagnosing.value || repairing.value || elevatedRepairing.value)

async function runDiagnosis() {
  diagnosing.value = true
  repairError.value = ''
  try {
    const result = await diagnoseDatabase()
    diagnosis.value = result
    addLog(`数据库诊断完成：quick_check=${result.quick_check}，缺失索引=${result.missing_thread_records}，JSONL 待修正=${result.session_meta_status?.mismatched_session_meta || 0}。`)
    if (result.issues?.length) {
      showToast(`数据库诊断发现问题: ${result.issues.join('；')}`, 'error')
    } else if (result.recommendations?.length) {
      showToast('数据库诊断完成，发现可修复项', 'info')
    } else {
      showToast('数据库诊断完成，未发现明显问题', 'success')
    }
  } catch (e) {
    repairError.value = e.message
    addLog(`数据库诊断失败: ${e.message}`)
    showToast(`数据库诊断失败: ${e.message}`, 'error')
  } finally {
    diagnosing.value = false
  }
}

async function runRepair(elevated) {
  repairError.value = ''
  repairResult.value = null
  if (elevated) {
    elevatedRepairing.value = true
  } else {
    repairing.value = true
  }
  try {
    const result = elevated ? await repairDatabaseElevated() : await repairDatabase()
    repairResult.value = result
    addLog(`${elevated ? '管理员权限修复' : '数据库修复'}完成：重建 ${result.inserted_threads} 条，补全文案 ${result.updated_text_threads} 条，JSONL ${result.updated_session_meta} 条。`)
    addLog(`修复前安全备份: ${result.backup_path}`)
    showToast('数据库修复完成', 'success')
    await runDiagnosis()
    emit('refresh')
  } catch (e) {
    repairError.value = e.message
    addLog(`${elevated ? '管理员权限修复' : '数据库修复'}失败: ${e.message}`)
    showToast(`${elevated ? '管理员权限修复' : '数据库修复'}失败: ${e.message}`, 'error')
  } finally {
    repairing.value = false
    elevatedRepairing.value = false
  }
}
</script>
