<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Delete } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { analyzeRepo, uploadRepo, deleteRepo, type AnalyzeResult } from '@/api'
import { repoStore, addRepo, removeRepo, syncRepos, getDemoRepoPath } from '@/stores/repos'

const targetRepo = ref('')
const customPrompt = ref('')
const analyzing = ref(false)
const uploading = ref(false)
const result = ref<AnalyzeResult | null>(null)
const showPrompt = ref(false)

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
    result.value = await analyzeRepo(targetRepo.value, customPrompt.value)
  } catch (e) {
    ElMessage.error('分析失败: ' + (e as Error).message)
  } finally {
    analyzing.value = false
  }
}

function renderMd(text: string): string {
  return marked.parse(text) as string
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
      <el-form-item>
        <el-button link type="primary" @click="showPrompt = !showPrompt">
          {{ showPrompt ? '收起提示词' : '自定义提示词（可选）' }}
        </el-button>
      </el-form-item>
      <el-form-item v-if="showPrompt">
        <el-input
          v-model="customPrompt"
          type="textarea"
          :rows="3"
          placeholder="例如：重点关注安全问题、只分析核心模块、用英文输出..."
        />
      </el-form-item>
      <el-button type="primary" :loading="analyzing" @click="onAnalyze">分析</el-button>
    </el-form>
  </el-card>

  <el-card v-if="result">
    <template #header>分析报告</template>
    <div class="md-body" v-html="renderMd(result.report)" />
  </el-card>
</template>

<style scoped>
.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3),
.md-body :deep(h4) {
  margin-top: 1.2em;
  margin-bottom: 0.5em;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.md-body :deep(h2) {
  padding-bottom: 0.3em;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.md-body :deep(p) {
  margin: 0.6em 0;
  line-height: 1.8;
}
.md-body :deep(ul),
.md-body :deep(ol) {
  padding-left: 1.8em;
  margin: 0.5em 0;
}
.md-body :deep(li) {
  margin: 0.3em 0;
  line-height: 1.7;
}
.md-body :deep(code) {
  background: var(--el-fill-color-light);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: 'Menlo', 'Monaco', 'Consolas', monospace;
}
.md-body :deep(pre) {
  background: var(--el-fill-color-dark);
  color: var(--el-text-color-primary);
  padding: 1em;
  border-radius: 8px;
  overflow-x: auto;
  margin: 0.8em 0;
}
.md-body :deep(pre code) {
  background: none;
  padding: 0;
}
.md-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.8em 0;
}
.md-body :deep(th),
.md-body :deep(td) {
  border: 1px solid var(--el-border-color-lighter);
  padding: 0.5em 0.8em;
  text-align: left;
}
.md-body :deep(th) {
  background: var(--el-fill-color-light);
  font-weight: 600;
}
.md-body :deep(blockquote) {
  border-left: 4px solid var(--el-color-primary);
  padding-left: 1em;
  margin: 0.8em 0;
  color: var(--el-text-color-secondary);
}
.md-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--el-border-color-lighter);
  margin: 1.5em 0;
}
</style>
