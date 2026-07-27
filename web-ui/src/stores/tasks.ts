import { reactive, watch } from 'vue'

export interface TaskRecord {
  task_id: string
  goal: string
  target_repo: string
  submitted_at: string
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
