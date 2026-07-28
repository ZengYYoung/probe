<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Delete, Refresh } from '@element-plus/icons-vue'
import { submitTask, getReport, getStream, uploadRepo, deleteRepo, type RunResult, type Step } from '@/api'
import { taskStore, addTask, updateTaskStatus, removeTask, clearTasks, syncTasks, type TaskRecord } from '@/stores/tasks'
import { repoStore, addRepo, removeRepo, syncRepos, getDemoRepoPath } from '@/stores/repos'

const goal = ref('')
const targetRepo = ref('')
const submitting = ref(false)
const uploading = ref(false)

const drawerVisible = ref(false)
const current = ref<RunResult | null>(null)
const currentSteps = ref<Step[]>([])
const currentRecord = ref<TaskRecord | null>(null)

const pollingTimers: Record<string, ReturnType<typeof setInterval>> = {}

const statusType: Record<string, string> = {
  RUNNING: 'primary',
  SUCCESS: 'success',
  BLOCKED_NO_PROGRESS: 'danger',
  STOPPED_REJECTED: 'warning',
  STOPPED_BUDGET: 'warning',
  ERROR: 'danger',
}

onMounted(async () => {
  await syncRepos()
  await syncTasks()
  // Default to the built-in demo repo if nothing is selected.
  if (!targetRepo.value) {
    targetRepo.value = getDemoRepoPath() || ''
  }
})

async function onUpload(file: File) {
  uploading.value = true
  try {
    const resp = await uploadRepo(file)
    addRepo({ repo_id: resp.repo_id, path: resp.path, name: resp.name, file_count: resp.file_count, is_demo: false })
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

async function onDeleteRepo(repoId: string) {
  if (repoId === 'demo') {
    ElMessage.warning('内置 demo 不可删除')
    return
  }
  try {
    await ElMessageBox.confirm('删除该 repo？解压目录会被清理。', '确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteRepo(repoId)
    removeRepo(repoId)
    if (targetRepo.value && !repoStore.some((r) => r.path === targetRepo.value)) {
      targetRepo.value = getDemoRepoPath() || ''
    }
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error('删除失败: ' + (e as Error).message)
  }
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
      status: 'RUNNING',
    })
    ElMessage.success(`已提交，agent 正在后台运行…`)
    goal.value = ''
    startPolling(resp.task_id)
  } catch (e) {
    ElMessage.error('提交失败: ' + (e as Error).message)
  } finally {
    submitting.value = false
  }
}

function startPolling(taskId: string) {
  if (pollingTimers[taskId]) return
  pollingTimers[taskId] = setInterval(async () => {
    try {
      const rep = await getReport(taskId)
      if (rep.status !== 'RUNNING') {
        updateTaskStatus(taskId, rep.status)
        clearInterval(pollingTimers[taskId])
        delete pollingTimers[taskId]
        ElMessage.success(`任务 ${taskId.slice(0, 8)}… 完成: ${rep.status}`)
      }
    } catch {
      // Task no longer exists on backend — remove from history.
      removeTask(taskId)
      clearInterval(pollingTimers[taskId])
      delete pollingTimers[taskId]
      ElMessage.warning(`任务 ${taskId.slice(0, 8)}… 已失效（服务器已重启）`)
    }
  }, 2000)
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

function onDelete(rec: TaskRecord) {
  removeTask(rec.task_id)
  if (pollingTimers[rec.task_id]) {
    clearInterval(pollingTimers[rec.task_id])
    delete pollingTimers[rec.task_id]
  }
}

function onClearAll() {
  ElMessageBox.confirm('确定清空所有任务历史？', '提示', { type: 'warning' })
    .then(() => {
      Object.keys(pollingTimers).forEach(id => clearInterval(pollingTimers[id]))
      Object.keys(pollingTimers).forEach(id => delete pollingTimers[id])
      clearTasks()
      ElMessage.success('已清空')
    })
    .catch(() => {})
}

onUnmounted(() => {
  Object.keys(pollingTimers).forEach(id => clearInterval(pollingTimers[id]))
})
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
          placeholder="选择 repo"
          style="width: calc(100% - 40px); margin-top: 8px"
          @change="onRepoSelect"
        >
          <el-option
            v-for="r in repoStore"
            :key="r.repo_id"
            :label="`${r.name} (${r.file_count} 文件)`"
            :value="r.path"
          />
        </el-select>
        <el-button
          v-if="repoStore.length && repoStore.find((r) => r.path === targetRepo) && !repoStore.find((r) => r.path === targetRepo)?.is_demo"
          :icon="Delete"
          link
          type="danger"
          style="margin-top: 8px; margin-left: 8px"
          @click="onDeleteRepo((repoStore.find((r) => r.path === targetRepo) || {}).repo_id)"
        />
      </el-form-item>
      <el-form-item label="或手动输入路径 (本地开发)">
        <el-input v-model="targetRepo" placeholder="/path/to/java-repo" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" @click="onSubmit">提交</el-button>
    </el-form>
  </el-card>

  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>任务历史</span>
        <el-button v-if="taskStore.length" :icon="Delete" link type="danger" @click="onClearAll">清空</el-button>
      </div>
    </template>
    <el-table :data="taskStore" empty-text="暂无任务">
      <el-table-column label="Task ID" width="120">
        <template #default="{ row }">{{ row.task_id.slice(0, 8) }}…</template>
      </el-table-column>
      <el-table-column prop="goal" label="Goal" show-overflow-tooltip />
      <el-table-column label="状态" width="160">
        <template #default="{ row }">
          <el-tag :type="statusType[row.status] || 'info'" :effect="row.status === 'RUNNING' ? 'dark' : 'light'">
            <el-icon v-if="row.status === 'RUNNING'" style="margin-right: 4px"><Refresh class="rotating" /></el-icon>
            {{ row.status || '未知' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ new Date(row.submitted_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button link type="primary" @click="viewDetail(row)">查看</el-button>
          <el-button link type="danger" :icon="Delete" @click="onDelete(row)" />
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

<style scoped>
.rotating { animation: rotate 1.5s linear infinite; }
@keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
