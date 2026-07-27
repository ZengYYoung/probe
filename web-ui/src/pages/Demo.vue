<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getDemo, type DemoResp } from '@/api'

const loading = ref(false)
const result = ref<DemoResp | null>(null)

async function runAll() {
  loading.value = true
  result.value = null
  try {
    result.value = await getDemo()
  } catch (e) {
    ElMessage.error('演示失败: ' + (e as Error).message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-card style="margin-bottom: 16px">
    <el-button type="primary" :loading="loading" @click="runAll">运行全部演示</el-button>
    <span style="margin-left: 12px; color: var(--el-text-color-secondary); font-size: 12px">
      纯 mock，无 key 无网络，确定性可复现
    </span>
  </el-card>

  <el-row :gutter="16" v-if="result">
    <el-col :span="8">
      <el-card>
        <template #header>① 护栏拦截</template>
        <el-alert type="error" :closable="false" :title="result.guardrail" />
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card>
        <template #header>② 反馈闭环</template>
        <el-timeline v-if="result.feedback_loop.length">
          <el-timeline-item v-for="(line, i) in result.feedback_loop" :key="i" :timestamp="`step ${i + 1}`">
            {{ line }}
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="无步骤" />
      </el-card>
    </el-col>
    <el-col :span="8">
      <el-card>
        <template #header>③ 无进展停机</template>
        <el-alert type="warning" :closable="false" :title="result.no_progress" />
      </el-card>
    </el-col>
  </el-row>
  <el-skeleton v-else-if="loading" :rows="6" animated />
</template>
