<template>
  <div class="app-root">
    <!-- Loading Splash (shown while backend initializes) -->
    <Transition name="splash-fade">
      <div v-if="isLoading" class="app-splash">
        <div class="app-splash-content">
          <div class="app-splash-logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          </div>
          <h1 class="app-splash-title">Codex History Sync</h1>
          <p class="app-splash-status">{{ loadingMessage }}</p>
          <div class="app-splash-progress">
            <div class="app-splash-bar"></div>
          </div>
          <p class="app-splash-hint">首次启动可能需要几秒初始化后端服务</p>
        </div>
      </div>
    </Transition>

    <!-- Main UI (hidden while loading) -->
    <template v-if="!isLoading">
    <!-- Custom Title Bar -->
    <div class="titlebar" @dblclick="toggleMaximize">
      <div class="titlebar-brand">
        <div class="titlebar-logo">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
        </div>
        <span class="titlebar-title">Codex History Sync</span>
      </div>
      <div class="titlebar-controls">
        <button class="titlebar-btn" @click="minimize" title="最小化">
          <svg width="12" height="12" viewBox="0 0 12 12"><rect y="5" width="12" height="2" rx="1" fill="currentColor"/></svg>
        </button>
        <button class="titlebar-btn" @click="toggleMaximize" title="最大化">
          <svg width="12" height="12" viewBox="0 0 12 12"><rect x="1" y="1" width="10" height="10" rx="1.5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
        </button>
        <button class="titlebar-btn titlebar-btn-close" @click="close" title="关闭">
          <svg width="12" height="12" viewBox="0 0 12 12"><path d="M2 2L10 10M10 2L2 10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </button>
      </div>
    </div>

    <div class="app-body">
      <!-- Sidebar -->
      <aside class="sidebar">
        <div class="sidebar-brand">
          <div class="brand-icon">
            <div class="brand-dot"></div>
          </div>
          <div class="brand-text">
            <h1 class="brand-name">Codex Sync</h1>
            <span class="brand-badge">LOCAL</span>
          </div>
          <p class="brand-desc">本地历史修复与备份恢复</p>
        </div>

        <nav class="sidebar-nav">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: $route.path === item.path }"
          >
            <span class="nav-icon" v-html="item.icon"></span>
            <span class="nav-label">{{ item.label }}</span>
          </router-link>
        </nav>

        <div class="sidebar-status">
          <div class="status-card">
            <div class="status-title">本机状态</div>
            <div class="status-row">
              <span class="status-label">当前 Provider</span>
              <span class="status-value">{{ status?.current_provider || '--' }}</span>
            </div>
            <div class="status-row">
              <span class="status-label">当前模型</span>
              <span class="status-value status-value-sm">{{ status?.current_model || '--' }}</span>
            </div>
            <div class="status-row">
              <span class="status-label">可恢复备份</span>
              <span class="status-value accent">{{ status?.backups?.length || 0 }} 份</span>
            </div>
            <div class="status-hint" :class="hintClass">
              {{ hintMessage }}
            </div>
          </div>
        </div>

        <div class="sidebar-footer">
          适用于 Codex Desktop 本地历史修复
        </div>
      </aside>

      <!-- Main Content -->
      <main class="main-content">
        <router-view
          :status="status"
          :logs="logs"
          @refresh="refreshStatus"
          @log="addLog"
          v-slot="{ Component }"
        >
          <component :is="Component" ref="currentView" />
        </router-view>
      </main>
    </div>

    <!-- Toast Notifications -->
    <Toast ref="toastRef" />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, provide, nextTick } from 'vue'
import { getStatus } from './api.js'
import Toast from './components/Toast.vue'

const isLoading = ref(true)
const loadingMessage = ref('正在初始化...')
const status = ref(null)
const logs = ref([])
const toastRef = ref(null)

const navItems = [
  {
    path: '/overview',
    label: '概览',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>'
  },
  {
    path: '/sync',
    label: '历史同步',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>'
  },
  {
    path: '/backups',
    label: '备份恢复',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>'
  },
  {
    path: '/logs',
    label: '操作日志',
    icon: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>'
  }
]

const hintClass = computed(() => {
  if (!status.value) return ''
  return status.value.movable_threads > 0 ? 'warning' : 'success'
})

const hintMessage = computed(() => {
  if (!status.value) return '先刷新状态，再决定是否同步。'
  if (status.value.movable_threads > 0) {
    return `有 ${status.value.movable_threads} 条线程待同步。`
  }
  return '当前已经是最新归档状态。'
})

function showToast(message, type = 'info') {
  toastRef.value?.addToast(message, type)
}

provide('addLog', addLog)
provide('showToast', showToast)

function addLog(message) {
  const now = new Date()
  const ts = now.toLocaleTimeString('zh-CN', { hour12: false })
  logs.value.unshift({ time: ts, message })
  if (logs.value.length > 200) logs.value.pop()
}

async function refreshStatus() {
  try {
    status.value = await getStatus()
    addLog(`状态已刷新。当前 provider=${status.value.current_provider}，可同步线程=${status.value.movable_threads}。`)
  } catch (e) {
    addLog(`刷新失败: ${e.message}`)
    showToast(`刷新失败: ${e.message}`, 'error')
    throw e
  }
}

function minimize() {
  window.codexAPI.minimize()
}
function toggleMaximize() {
  window.codexAPI.maximize()
}
function close() {
  window.codexAPI.close()
}

// Fade out the pre-Vue HTML splash once Vue takes over
function dismissPreSplash() {
  const el = document.getElementById('pre-splash')
  if (el) {
    el.classList.add('fade-out')
    setTimeout(() => el.remove(), 600)
  }
}

async function bootApp() {
  // Step 1: brief delay so user sees the splash
  loadingMessage.value = '正在连接后端服务...'
  await new Promise(r => setTimeout(r, 400))

  // Step 2: actually call backend
  loadingMessage.value = '正在读取本地状态...'
  try {
    const result = await getStatus()
    status.value = result
    addLog(`状态已就绪。当前 provider=${result.current_provider}，可同步线程=${result.movable_threads}。`)
    loadingMessage.value = '加载完成'
  } catch (e) {
    addLog(`启动失败: ${e.message}`)
    showToast(`后端连接失败: ${e.message}`, 'error')
    loadingMessage.value = '部分功能可能不可用'
  }

  // Step 3: brief pause then fade out splash
  await new Promise(r => setTimeout(r, 500))
  isLoading.value = false
  await nextTick()
  dismissPreSplash()
}

onMounted(() => {
  bootApp()
})
</script>
