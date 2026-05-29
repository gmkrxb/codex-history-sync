<template>
  <div class="view">
    <div class="view-header">
      <div>
        <h2 class="view-title">概览</h2>
        <p class="view-desc">管理本地历史同步、备份恢复与数据库状态。</p>
      </div>
      <div class="header-actions">
        <span class="badge" :class="status?.movable_threads > 0 ? 'badge-warning' : 'badge-success'">
          {{ status?.movable_threads > 0 ? `待同步 ${status.movable_threads} 条` : '状态正常' }}
        </span>
        <button class="btn btn-secondary" @click="$emit('refresh')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          刷新状态
        </button>
      </div>
    </div>

    <!-- Hero Card -->
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
        <div class="hero-warning" v-if="status?.movable_threads > 0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          <span>建议先关闭 Codex Desktop 再执行同步或恢复</span>
        </div>
      </div>
    </div>

    <!-- Metric Cards -->
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
      <div class="card metric-card" :class="status?.movable_threads > 0 ? 'metric-warn' : 'metric-ok'">
        <div class="metric-label">待同步线程</div>
        <div class="metric-value">{{ status?.movable_threads ?? '--' }}</div>
        <div class="metric-meta">
          {{ status?.movable_threads > 0 ? '这些线程会在同步时并入当前 provider' : '当前已经全部归到正在使用的 provider 下面' }}
        </div>
      </div>
      <div class="card metric-card">
        <div class="metric-label">线程总数</div>
        <div class="metric-value">{{ status?.total_threads ?? '--' }}</div>
        <div class="metric-meta">共发现 {{ status?.provider_counts?.length || 0 }} 个 provider</div>
        <div class="metric-hint">可用备份 {{ status?.backups?.length || 0 }} 份</div>
      </div>
    </div>

    <!-- Provider Stats -->
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
defineProps({
  status: Object,
  logs: Array
})
defineEmits(['refresh', 'log'])
</script>
