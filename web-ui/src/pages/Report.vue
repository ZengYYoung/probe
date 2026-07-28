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

  <el-card v-if="result">
    <template #header>分析报告</template>
    <pre class="report">{{ result.report }}</pre>
  </el-card>
</template>

<style scoped>
.report {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
}
</style>
