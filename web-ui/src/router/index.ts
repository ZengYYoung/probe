import { createRouter, createWebHashHistory } from 'vue-router'
import Tasks from '@/pages/Tasks.vue'
import CodeMap from '@/pages/CodeMap.vue'
import Approval from '@/pages/Approval.vue'
import Demo from '@/pages/Demo.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/tasks' },
    { path: '/tasks', name: 'tasks', component: Tasks },
    { path: '/map', name: 'map', component: CodeMap },
    { path: '/approval', name: 'approval', component: Approval },
    { path: '/demo', name: 'demo', component: Demo },
  ],
})

export default router
