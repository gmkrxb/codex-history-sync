<template>
  <div class="view">
    <div class="view-header">
      <div>
        <h2 class="view-title">操作日志</h2>
        <p class="view-desc">记录刷新、同步、备份和恢复的执行结果。</p>
      </div>
      <div class="header-actions">
        <button class="btn btn-secondary" @click="clearLogs">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          清空日志
        </button>
      </div>
    </div>

    <div class="card log-card">
      <div class="log-list" v-if="logs.length">
        <div v-for="(log, index) in logs" :key="index" class="log-entry">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.message }}</span>
        </div>
      </div>
      <div class="empty-state" v-else>
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        <p>暂无操作日志</p>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  status: Object,
  logs: Array
})
const emit = defineEmits(['refresh', 'log'])

function clearLogs() {
  props.logs.length = 0
}
</script>
