import { createRouter, createWebHashHistory } from 'vue-router'
import Report from '@/pages/Report.vue'
import CodeMap from '@/pages/CodeMap.vue'
import Demo from '@/pages/Demo.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/report' },
    { path: '/report', name: 'report', component: Report },
    { path: '/map', name: 'map', component: CodeMap },
    { path: '/demo', name: 'demo', component: Demo },
  ],
})

export default router
