const base = ''

export interface TaskCreateResp { task_id: string }
export interface Step {
  iteration: number
  action: { type: string; command?: string; path?: string; params?: Record<string, unknown> }
  tool_result?: { ok?: boolean; output?: string; error?: string }
  failure_report?: unknown
  decision?: { action?: string; reason?: string; context_fragment?: string } | null
}
export interface RunResult {
  status: string
  steps: Step[]
  final_failure_report?: unknown
  report_path?: string | null
}
export interface DemoResp {
  guardrail: string
  feedback_loop: string[]
  no_progress: string
}

export async function submitTask(goal: string, target_repo: string): Promise<TaskCreateResp> {
  const r = await fetch(`${base}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal, target_repo }),
  })
  if (!r.ok) throw new Error(`submitTask ${r.status}`)
  return r.json()
}

export async function getReport(taskId: string): Promise<RunResult> {
  const r = await fetch(`${base}/tasks/${taskId}/report`)
  if (!r.ok) throw new Error(`getReport ${r.status}`)
  return r.json()
}

export async function getStream(taskId: string): Promise<{ steps: Step[] }> {
  const r = await fetch(`${base}/tasks/${taskId}/stream`)
  if (!r.ok) throw new Error(`getStream ${r.status}`)
  return r.json()
}

export async function approveTask(taskId: string, approve: boolean): Promise<{ ok: boolean }> {
  const r = await fetch(`${base}/tasks/${taskId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approve }),
  })
  if (!r.ok) throw new Error(`approveTask ${r.status}`)
  return r.json()
}

export async function getPackageDot(repo: string): Promise<string> {
  const r = await fetch(`${base}/map/package.dot?repo=${encodeURIComponent(repo)}`)
  if (!r.ok) throw new Error(`getPackageDot ${r.status}`)
  return r.text()
}

export async function getClassDot(repo: string, pkg?: string): Promise<string> {
  let url = `${base}/map/class.dot?repo=${encodeURIComponent(repo)}`
  if (pkg) url += `&package=${encodeURIComponent(pkg)}`
  const r = await fetch(url)
  if (!r.ok) throw new Error(`getClassDot ${r.status}`)
  return r.text()
}

export async function getDemo(): Promise<DemoResp> {
  const r = await fetch(`${base}/demo`)
  if (!r.ok) throw new Error(`getDemo ${r.status}`)
  return r.json()
}

export interface RepoUploadResp { repo_id: string; path: string; name: string; file_count: number }
export interface RepoListItem { repo_id: string; name: string; file_count: number; path: string; is_demo: boolean }

export interface AnalyzeFailure {
  validator: string
  severity: string
  file: string
  line: number | null
  category: string
  message: string
  hint: string
}
export interface AnalyzeResult {
  per_validator_status: Record<string, string>
  failures: AnalyzeFailure[]
  signature: string
  summary: Record<string, number>
}

export async function analyzeRepo(target_repo: string): Promise<AnalyzeResult> {
  const r = await fetch(`${base}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_repo }),
  })
  if (!r.ok) throw new Error(`analyze ${r.status}`)
  return r.json()
}

export async function uploadRepo(file: File): Promise<RepoUploadResp> {
  const fd = new FormData()
  fd.append('file', file)
  const r = await fetch(`${base}/repos/upload`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(`uploadRepo ${r.status}`)
  return r.json()
}

export async function listRepos(): Promise<RepoListItem[]> {
  const r = await fetch(`${base}/repos`)
  if (!r.ok) throw new Error(`listRepos ${r.status}`)
  return r.json()
}

export async function getRepo(repoId: string): Promise<RepoUploadResp> {
  const r = await fetch(`${base}/repos/${repoId}`)
  if (!r.ok) throw new Error(`getRepo ${r.status}`)
  return r.json()
}

export async function deleteRepo(repoId: string): Promise<{ ok: boolean }> {
  const r = await fetch(`${base}/repos/${repoId}`, { method: 'DELETE' })
  if (!r.ok) throw new Error(`deleteRepo ${r.status}`)
  return r.json()
}
