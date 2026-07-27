# Java 项目上传功能 设计文档

> 日期：2026-07-27
> 主题：为 WebUI 新增上传 Java 项目（zip）功能，使部署在 Render 上的用户能提供自己的 Java 仓给 agent 和代码地图使用。
> 约束：不触碰 harness 内核；不改现有端点契约；前端无 pytest（`npm run build` 为验证门）。

---

## 1. 目标与边界

### 1.1 目标
- 新增 `POST /repos/upload` 端点：接收 zip → 安全解压到临时目录 → 返回 `{repo_id, path, name, file_count}`。
- 新增 `GET /repos` 端点：列出已上传的 repo，供前端下拉选择。
- 前端 Tasks 页和 CodeMap 页加 `el-upload` + repo 下拉，上传后自动填入 path。
- 新增 `stores/repos.ts` 客户端 repo 列表（reactive + localStorage），两页共享。
- 新增 `tests/web/test_repos_upload.py` 端点测试（mock，无 key 无网络）。

### 1.2 非目标（YAGNI）
- 不做 git URL clone（用户只选了 zip 上传）。
- 不做 TTL / 定时清理临时目录（单节点 dev/ops 面，进程退出即清理）。
- 不做持久化 repo 存储（进程内 dict，重启即失）。
- 不改 `POST /tasks` / `/map/*.dot` 的请求/响应形状（它们仍接受 path 字符串，前端传上传返回的 path）。
- 不做异步 agent 运行（`POST /tasks` 仍同步，上传只提供 repo，不改变 agent 运行模式）。

### 1.3 硬约束
- 不触碰 harness 内核（`probe/core`、`probe/llm`、`probe/tools`、`probe/guardrail`、`probe/validators`、`probe/feedback`、`probe/codemap`、`probe/memory`、`probe/report`）。
- 现有端点契约不变：`POST /tasks`、`GET /tasks/{id}/report`、`GET /tasks/{id}/stream`、`POST /tasks/{id}/approve`、`GET /map/package.dot`、`GET /map/class.dot`、`GET /demo` 的请求/响应形状不动。
- `tests/web/test_app.py` + `tests/web/test_demo_endpoint.py` 保持绿。
- `make test` 命令不变。
- 前端无 pytest：以 `npm run build` 成功为验证门。

---

## 2. 后端设计（`probe/web/app.py`，外壳层）

### 2.1 进程内 repo store
在 `create_app` 内新增（与现有 `tasks` / `approvals` store 同模式）：
```python
repos: dict[str, dict] = {}  # repo_id -> {path, name, file_count}
```

### 2.2 `POST /repos/upload`
- 请求：multipart/form-data，字段名 `file`，值为 zip 文件。
- 校验：
  - 文件名以 `.zip` 结尾（不区分大小写）。
  - magic bytes 前 4 字节为 `PK\x03\x04` 或 `PK\x05\x06`（空 zip 也算合法 magic）。
  - 大小 ≤ 50MB（`len(content) <= 50 * 1024 * 1024`）。
- 解压：
  - 生成 `repo_id = uuid.uuid4().hex`。
  - 解压目录 `tempfile.mkdtemp(prefix=f"probe-repo-{repo_id}-")`。
  - **Zip slip 防护**：遍历 `zipfile.ZipFile.infolist()`，对每个 entry，`Path(dest_dir) / entry.filename` resolve 后必须仍在 `dest_dir` 内（`is_relative_to` 检查），否则 400 拒绝整个上传。
  - 解压后统计 `file_count`（递归文件数）。
- 存储：`repos[repo_id] = {"path": str(dest), "name": filename, "file_count": file_count}`。
- 响应：`{"repo_id": str, "path": str, "name": str, "file_count": int}`。

### 2.3 `GET /repos`
- 响应：`[{"repo_id": str, "name": str, "file_count": int}]`（不含 path，避免泄露服务端路径到列表接口；path 仅在上传响应和 `/repos/{repo_id}` 中返回）。

### 2.4 `GET /repos/{repo_id}`
- 响应：`{"repo_id": str, "path": str, "name": str, "file_count": int}`。
- 404 if not found。
- 前端用此在页面刷新后从 localStorage 的 repo_id 取回 path（进程重启后 path 失效，前端应处理 404 → 提示重新上传）。

### 2.5 不改的端点
`POST /tasks` 的 `target_repo` 仍是路径字符串。前端传上传返回的 `path`。`safe_path` 围栏在 agent 工具层自然生效（`--repo` = 解压目录）。

---

## 3. 前端设计

### 3.1 `web-ui/src/stores/repos.ts`（新建）
```ts
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
```

### 3.2 `web-ui/src/api.ts` 新增
```ts
export interface RepoUploadResp { repo_id: string; path: string; name: string; file_count: number }
export interface RepoListItem { repo_id: string; name: string; file_count: number }

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
```

### 3.3 Tasks 页改动
- `target_repo` 输入旁加 `el-upload`（drag 区域，accept `.zip`，`:auto-upload="false"`，`:on-change` 手动触发 `uploadRepo`）。
- 上传成功 → `addRepo({repo_id, path, name, file_count})` → `targetRepo.value = path`。
- 加 `el-select` 下拉已上传 repo（从 `repoStore`），选中后 `targetRepo.value = repo.path`。
- 保留手动输入路径（本地开发用）。

### 3.4 CodeMap 页改动
- `repo` 输入旁加同样的 `el-upload` + `el-select` 下拉。
- 上传/选择后 → `repo.value = path` → 触发渲染。

---

## 4. 安全

- **Zip slip**：解压前逐条 `is_relative_to` 校验，越界即 400。
- **大小限制**：50MB，超限 413。
- **文件类型**：扩展名 + magic bytes 双校验。
- **临时目录**：`tempfile.mkdtemp` 权限 700（系统默认）；进程退出即清理（YAGNI 无 TTL）。
- **路径围栏**：`safe_path` 在 agent 工具层已生效，上传 repo 作为 `--repo` 自动受保护。
- **path 不泄露到列表接口**：`GET /repos` 只返回 `repo_id/name/file_count`，path 仅在 `POST /repos/upload` 和 `GET /repos/{id}` 返回。

---

## 5. 测试

### 5.1 新增 `tests/web/test_repos_upload.py`
- `test_upload_valid_zip`：构造一个含 `pom.xml` + `src/Main.java` 的 zip，上传 → 200 + repo_id + path 存在 + file_count >= 2。
- `test_upload_non_zip`：上传 `.txt` → 400。
- `test_upload_bad_magic`：文件名 `.zip` 但 magic bytes 不对 → 400。
- `test_upload_oversized`：构造 > 50MB 的 zip → 413（或 400）。
- `test_upload_zip_slip`：构造含 `../../evil.txt` 条目的 zip → 400。
- `test_list_repos`：上传后 `GET /repos` → 列表含该 repo。
- `test_get_repo`：上传后 `GET /repos/{id}` → 返回 path。
- `test_get_repo_404`：不存在的 repo_id → 404。

### 5.2 保持绿
- `tests/web/test_app.py`：端点契约不变。
- `tests/web/test_demo_endpoint.py`：不变。
- `make test` 命令不变。

---

## 6. 文件改动清单

| 文件 | 改动 |
|---|---|
| `probe/web/app.py` | 新增 `POST /repos/upload` + `GET /repos` + `GET /repos/{repo_id}` + 进程内 repo store + zip 解压与安全校验 |
| `web-ui/src/api.ts` | 新增 `uploadRepo` / `listRepos` / `getRepo` + TS 接口 |
| `web-ui/src/stores/repos.ts`（新） | reactive + localStorage repo 列表 |
| `web-ui/src/pages/Tasks.vue` | 加 `el-upload` + repo `el-select` 下拉 |
| `web-ui/src/pages/CodeMap.vue` | 加 `el-upload` + repo `el-select` 下拉 |
| `tests/web/test_repos_upload.py`（新） | 上传端点测试 |
| `README.md` | 运行节加一行说明上传功能 |

---

## 7. 风险与未决问题

- **进程重启后上传的 repo 失效**：进程内 store，重启即失。前端 localStorage 存的 repo_id 在 `GET /repos/{id}` 404 时应提示"repo 已失效，请重新上传"。这是单节点 dev/ops 面的已知限制，文档化即可。
- **大文件上传超时**：Render 免费层可能有请求超时。50MB 限制 + Render 的 100s 超时通常够用；若不够，后续可加分块上传（YAGNI）。
- **并发上传**：进程内 dict 非线程安全，但 uvicorn 单 worker 同步端点不会并发（`POST /tasks` 已是同步模式）。若多 worker 部署需加锁（YAGNI）。
- **`python-multipart` 依赖**：FastAPI 文件上传需 `python-multipart`。当前 `pyproject.toml` 未列此依赖。需在 `dependencies` 加 `python-multipart`，或在 `app.py` 内延迟 import + 友好报错。实现时确认。
