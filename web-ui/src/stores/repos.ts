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

export function removeRepo(repoId: string) {
  const i = repoStore.findIndex((r) => r.repo_id === repoId)
  if (i !== -1) repoStore.splice(i, 1)
}
