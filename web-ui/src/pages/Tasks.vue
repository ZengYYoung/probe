<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { submitTask, getReport, getStream, uploadRepo, type RunResult, type Step } from '@/api'
import { taskStore, addTask, type TaskRecord } from '@/stores/tasks'
import { repoStore, addRepo } from '@/stores/repos'

const goal = ref('')
const targetRepo = ref('')
const submitting = ref(false)
const uploading = ref(false)

const drawerVisible = ref(false)
const current = ref<RunResult | null>(null)
const currentSteps = ref<Step[]>([])
const currentRecord = ref<TaskRecord | null>(null)

const statusType: Record<string, string> = {
  SUCCESS: 'success',
  BLOCKED_NO_PROGRESS: 'danger',
  STOPPED_REJECTED: 'warning',
  STOPPED_BUDGET: 'warning',
  ERROR: 'danger',
}

async function onUpload(file: File) {
  uploading.value = true
  try {
    const resp = await uploadRepo(file)
    addRepo({ repo_id: resp.repo_id, path: resp.path, name: resp.name, file_count: resp.file_count })
    targetRepo.value = resp.path
    ElMessage.success(`已上传: ${resp.name} (${resp.file_count} 文件)`)
  } catch (e) {
    ElMessage.error('上传失败: ' + (e as Error).message)
  } finally {
    uploading.value = false
  }
}

function onRepoSelect(path: string) {
  targetRepo.value = path
}

async function onSubmit() {
  if (!goal.value || !targetRepo.value) {
    ElMessage.warning('请填写 goal 并上传/选择 repo')
    return
  }
  submitting.value = true
  try {
    const resp = await submitTask(goal.value, targetRepo.value)
    addTask({
      task_id: resp.task_id,
      goal: goal.value,
      target_repo: targetRepo.value,
      submitted_at: new Date().toISOString(),
    })
    ElMessage.success(`已提交: ${resp.task_id.slice(0, 8)}…`)
    goal.value = ''
  } catch (e) {
    ElMessage.error('提交失败: ' + (e as Error).message)
  } finally {
    submitting.value = false
  }
}

async function viewDetail(rec: TaskRecord) {
  currentRecord.value = rec
  drawerVisible.value = true
  current.value = null
  currentSteps.value = []
  try {
    const [rep, stream] = await Promise.all([
      getReport(rec.task_id),
      getStream(rec.task_id),
    ])
    current.value = rep
    currentSteps.value = stream.steps
  } catch (e) {
    ElMessage.error('加载详情失败: ' + (e as Error).message)
  }
}
</script>

<template>
  <el-card style="margin-bottom: 16px">
    <template #header>提交任务</template>
    <el-form label-position="top">
      <el-form-item label="目标 (goal)">
        <el-input v-model="goal" type="textarea" :rows="2" placeholder="让测试变绿" />
      </el-form-item>
      <el-form-item label="Java 项目 (上传 zip 或选择已上传)">
        <el-upload
          :auto-upload="true"
          :show-file-list="false"
          accept=".zip"
          :http-request="(opts: any) => onUpload(opts.file)"
        >
          <el-button :icon="Upload" :loading="uploading">上传 zip</el-button>
        </el-upload>
        <el-select
          v-if="repoStore.length"
          v-model="targetRepo"
          placeholder="选择已上传的 repo"
          style="width: 100%; margin-top: 8px"
          @change="onRepoSelect"
        >
          <el-option
            v-for="r in repoStore"
            :key="r.repo_id"
            :label="`${r.name} (${r.file_count} 文件)`"
            :value="r.path"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="或手动输入路径 (本地开发)">
        <el-input v-model="targetRepo" placeholder="/path/to/java-repo" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" @click="onSubmit">提交</el-button>
    </el-form>
  </el-card>

  <el-card>
    <template #header>任务历史</template>
    <el-table :data="taskStore" empty-text="暂无任务">
      <el-table-column label="Task ID" width="140">
        <template #default="{ row }">{{ row.task_id.slice(0, 8) }}…</template>
      </el-table-column>
      <el-table-column prop="goal" label="Goal" show-overflow-tooltip />
      <el-table-column label="提交时间" width="180">
        <template #default="{ row }">{{ new Date(row.submitted_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button link type="primary" @click="viewDetail(row)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-drawer v-model="drawerVisible" size="50%" :title="currentRecord?.goal">
    <template v-if="current">
      <el-tag :type="statusType[current.status] || 'info'" style="margin-bottom: 12px">
        {{ current.status }}
      </el-tag>
      <h4>步骤时间线</h4>
      <el-timeline v-if="currentSteps.length">
        <el-timeline-item v-for="s in currentSteps" :key="s.iteration" :timestamp="`iter ${s.iteration}`">
          <div><strong>action:</strong> {{ s.action.type }}</div>
          <div v-if="s.action.path"><strong>path:</strong> {{ s.action.path }}</div>
          <div v-if="s.action.command"><strong>cmd:</strong> {{ s.action.command }}</div>
          <div v-if="s.decision?.reason"><strong>reason:</strong> {{ s.decision.reason }}</div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="无步骤" />
      <h4>最终报告</h4>
      <el-card shadow="never">
        <pre style="white-space: pre-wrap; font-size: 12px">{{ JSON.stringify(current.final_failure_report, null, 2) }}</pre>
      </el-card>
    </template>
    <el-skeleton v-else :rows="5" animated />
  </el-drawer>
</template>
