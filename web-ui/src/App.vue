<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  Document,
  Share,
  Cpu,
  Moon,
  Sunny,
} from '@element-plus/icons-vue'
import { syncRepos } from '@/stores/repos'

const route = useRoute()
const isDark = ref(false)

function applyDark(v: boolean) {
  document.documentElement.classList.toggle('dark', v)
  localStorage.setItem('probe-dark', String(v))
}

function toggleDark(v: boolean) {
  isDark.value = v
  applyDark(v)
}

onMounted(() => {
  const saved = localStorage.getItem('probe-dark') === 'true'
  isDark.value = saved
  applyDark(saved)
  // Clear stale task history from localStorage (task feature removed).
  localStorage.removeItem('probe-tasks')
  // Sync repos with backend — removes stale entries, adds built-in demo.
  syncRepos()
})

const menus = [
  { index: '/report', label: '代码报告', icon: Document },
  { index: '/map', label: '代码地图', icon: Share },
  { index: '/demo', label: '机制演示', icon: Cpu },
]
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside width="220px" style="background: #001529">
      <div style="padding: 20px 16px; color: #fff; font-size: 18px; font-weight: 600">
        Probe
      </div>
      <div style="padding: 0 16px 16px; color: #8c8c8c; font-size: 12px">
        Java 可行性 harness
      </div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#001529"
        text-color="#bfbfbf"
        active-text-color="#409eff"
      >
        <el-menu-item v-for="m in menus" :key="m.index" :index="m.index">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--el-border-color)">
        <span style="font-size: 16px; font-weight: 500">
          {{ menus.find(m => m.index === route.path)?.label || 'Probe' }}
        </span>
        <div style="display: flex; align-items: center; gap: 16px">
          <el-link href="https://github.com/ZengYYoung/probe" target="_blank" type="primary">
            GitHub
          </el-link>
          <el-switch
            :model-value="isDark"
            @update:model-value="toggleDark"
            :active-action-icon="Moon"
            :inactive-action-icon="Sunny"
          />
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
