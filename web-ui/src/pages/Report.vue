<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Delete } from '@element-plus/icons-vue'
import { analyzeRepo, uploadRepo, deleteRepo, type AnalyzeResult } from '@/api'
import { repoStore, addRepo, removeRepo, syncRepos, getDemoRepoPath } from '@/stores/repos'

const targetRepo = ref('')
const analyzing = ref(false)
const uploading = ref(false)
const result = ref<AnalyzeResult | null>(null)

const statusTag: Record<string, string> = {
  PASS: 'success',
  FAIL: 'danger',
  SKIPPED: 'info',
  UNAVAILABLE: 'warning',
  RUNNING: 'primary',
}

onMounted(async () => {
  await syncRepos()
  targetRepo.value = getDemoRepoPath() || ''
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

async function onDeleteRepo() {
  const cur = repoStore.find((r) => r.path === targetRepo.value)
  if (!cur || cur.is_demo) return
  try {
    await deleteRepo(cur.repo_id)
    removeRepo(cur.repo_id)
    targetRepo.value = getDemoRepoPath() || ''
    result.value = null
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error('删除失败: ' + (e as Error).message)
  }
}

async function onAnalyze() {
  if (!targetRepo.value) {
    ElMessage.warning('请选择一个 repo')
    return
  }
  analyzing.value = true
  result.value = null
  try {
    result.value = await analyzeRepo(targetRepo.value)
  } catch (e) {
    ElMessage.error('分析失败: ' + (e as Error).message)
  } finally {
    analyzing.value = false
  }
}
</script>

<template>
  <el-card style="margin-bottom: 16px">
    <template #header>代码分析</template>
    <el-form label-position="top">
      <el-form-item label="Java 项目">
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
        >
          <el-option
            v-for="r in repoStore"
            :key="r.repo_id"
            :label="`${r.name} (${r.file_count} 文件)`"
            :value="r.path"
          />
        </el-select>
        <el-button
          v-if="repoStore.find((r) => r.path === targetRepo && !r.is_demo)"
          :icon="Delete"
          link
          type="danger"
          style="margin-top: 8px; margin-left: 8px"
          @click="onDeleteRepo"
        />
      </el-form-item>
      <el-button type="primary" :loading="analyzing" @click="onAnalyze">分析</el-button>
    </el-form>
  </el-card>

  <template v-if="result">
    <el-card style="margin-bottom: 16px">
      <template #header>校验状态</template>
      <el-space wrap>
        <el-tag
          v-for="(status, name) in result.per_validator_status"
          :key="name"
          :type="(statusTag[status] as any) || 'info'"
          size="large"
          effect="dark"
        >
          {{ name }}: {{ status }}
        </el-tag>
      </el-space>
    </el-card>

    <el-card v-if="result.failures.length" style="margin-bottom: 16px">
      <template #header>
        问题列表
        <el-tag type="danger" style="margin-left: 8px">{{ result.failures.length }} 项</el-tag>
      </template>
      <el-table :data="result.failures" stripe border>
        <el-table-column label="校验器" prop="validator" width="100" />
        <el-table-column label="类别" prop="category" width="200" />
        <el-table-column label="文件" prop="file" show-overflow-tooltip />
        <el-table-column label="行" prop="line" width="70" />
        <el-table-column label="问题描述" prop="message" show-overflow-tooltip />
        <el-table-column label="建议" prop="hint" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card v-if="Object.keys(result.summary).length">
      <template #header>汇总</template>
      <el-space wrap>
        <el-tag v-for="(count, cat) in result.summary" :key="cat" type="warning">
          {{ cat }}: {{ count }}
        </el-tag>
      </el-space>
    </el-card>

    <el-card v-if="!result.failures.length" style="margin-top: 16px">
      <el-result icon="success" title="全部通过" sub-title="所有校验器均 PASS，未发现问题。" />
    </el-card>
  </template>
</template>
