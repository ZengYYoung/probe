import { reactive, watch } from 'vue'
import { listRepos } from '@/api'

export interface RepoRecord {
  repo_id: string
  path: string
  name: string
  file_count: number
  is_demo: boolean
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

export async function syncRepos() {
  try {
    const items = await listRepos()
    repoStore.splice(0, repoStore.length, ...items.map(r => ({
      repo_id: r.repo_id,
      path: r.path,
      name: r.name,
      file_count: r.file_count,
      is_demo: r.is_demo,
    })))
  } catch {
    // Backend unreachable — keep whatever is in localStorage.
  }
}

export function getDemoRepoPath(): string | undefined {
  return repoStore.find(r => r.is_demo)?.path
}
