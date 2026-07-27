<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { approveTask, getDemo } from '@/api'
import { taskStore } from '@/stores/tasks'

const selectedTaskId = ref('')
const guardrailResult = ref('')
const loading = ref(false)

async function onApprove(approve: boolean) {
  if (!selectedTaskId.value) {
    ElMessage.warning('请先选择任务')
    return
  }
  loading.value = true
  try {
    await approveTask(selectedTaskId.value, approve)
    ElMessage.success(approve ? '已批准' : '已拒绝')
  } catch (e) {
    ElMessage.error('操作失败: ' + (e as Error).message)
  } finally {
    loading.value = false
  }
}

async function runGuardrailDemo() {
  loading.value = true
  try {
    const d = await getDemo()
    guardrailResult.value = d.guardrail
  } catch (e) {
    ElMessage.error('演示失败: ' + (e as Error).message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-alert
    type="info"
    :closable="false"
    style="margin-bottom: 16px"
    title="说明"
    description="agent 主循环当前同步执行，此面板用于对已提交任务记录审批决策，并演示护栏对危险动作的确定性拦截。"
  />

  <el-card style="margin-bottom: 16px">
    <template #header>任务审批</template>
    <el-form inline>
      <el-form-item label="任务">
        <el-select v-model="selectedTaskId" placeholder="选择任务" style="width: 320px">
          <el-option
            v-for="t in taskStore"
            :key="t.task_id"
            :label="`${t.task_id.slice(0, 8)}… ${t.goal}`"
            :value="t.task_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="success" :loading="loading" @click="onApprove(true)">批准</el-button>
        <el-button type="danger" :loading="loading" @click="onApprove(false)">拒绝</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-card>
    <template #header>护栏确定性演示</template>
    <el-button type="primary" :loading="loading" @click="runGuardrailDemo">
      运行 rm -rf / 拦截演示
    </el-button>
    <el-alert
      v-if="guardrailResult"
      type="error"
      :closable="false"
      style="margin-top: 16px"
      :title="guardrailResult"
    />
  </el-card>
</template>
