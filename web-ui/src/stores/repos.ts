import { reactive, watch } from 'vue'

export interface RepoRecord {
  repo_id: string
  path: string
  name: string
  file_count: number
}

const KEY = 'probe-repos'

function load(): RepoRecord[] {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]') } catch { return [] }
}

export const repoStore = reactive<RepoRecord[]>(load())

watch(repoStore, (v) => {
  localStorage.setItem(KEY, JSON.stringify(v))
})

export function addRepo(rec: RepoRecord) {
  repoStore.unshift(rec)
}
