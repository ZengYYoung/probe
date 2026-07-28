import { reactive, watch } from 'vue'
import { getReport } from '@/api'

export interface TaskRecord {
  task_id: string
  goal: string
  target_repo: string
  submitted_at: string
  status?: string
}

const KEY = 'probe-tasks'

function load(): TaskRecord[] {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]') } catch { return [] }
}

export const taskStore = reactive<TaskRecord[]>(load())

watch(taskStore, (v) => {
  localStorage.setItem(KEY, JSON.stringify(v))
})

export function addTask(rec: TaskRecord) {
  taskStore.unshift(rec)
}

export function updateTaskStatus(taskId: string, status: string) {
  const t = taskStore.find(t => t.task_id === taskId)
  if (t) t.status = status
}

export function removeTask(taskId: string) {
  const i = taskStore.findIndex(t => t.task_id === taskId)
  if (i >= 0) taskStore.splice(i, 1)
}

export function clearTasks() {
  taskStore.splice(0, taskStore.length)
}

export async function syncTasks() {
  const stale: string[] = []
  await Promise.all(taskStore.map(async (t) => {
    try {
      const rep = await getReport(t.task_id)
      if (rep.status && rep.status !== 'RUNNING') {
        t.status = rep.status
      }
    } catch {
      stale.push(t.task_id)
    }
  }))
  stale.forEach(id => removeTask(id))
}
