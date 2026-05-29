import { createRouter, createWebHashHistory } from 'vue-router'
import Overview from './views/Overview.vue'
import Sync from './views/Sync.vue'
import Backups from './views/Backups.vue'
import Logs from './views/Logs.vue'

const routes = [
  { path: '/', redirect: '/overview' },
  { path: '/overview', name: 'Overview', component: Overview },
  { path: '/sync', name: 'Sync', component: Sync },
  { path: '/backups', name: 'Backups', component: Backups },
  { path: '/logs', name: 'Logs', component: Logs }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
