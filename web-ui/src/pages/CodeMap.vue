<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { graphviz } from 'd3-graphviz'
import { getPackageDot, getClassDot } from '@/api'

const repo = ref('')
const kind = ref<'package' | 'class'>('package')
const pkg = ref('')
const dotSource = ref('')
const loading = ref(false)
const graphContainer = ref<HTMLDivElement>()

async function render() {
  if (!repo.value) {
    ElMessage.warning('请填写 repo 路径（或留空使用内置 demo-repo）')
  }
  loading.value = true
  dotSource.value = ''
  try {
    const dot = kind.value === 'package'
      ? await getPackageDot(repo.value)
      : await getClassDot(repo.value, pkg.value || undefined)
    dotSource.value = dot
    await nextTick()
    if (graphContainer.value) {
      graphviz(graphContainer.value).renderDot(dot)
    }
  } catch (e) {
    ElMessage.error('渲染失败: ' + (e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  render()
})
</script>

<template>
  <el-card style="margin-bottom: 16px">
    <template #header>代码地图</template>
    <el-form inline>
      <el-form-item label="Repo">
        <el-input v-model="repo" placeholder="留空用内置 demo-repo" style="width: 320px" />
      </el-form-item>
      <el-form-item label="类型">
        <el-radio-group v-model="kind">
          <el-radio value="package">包图</el-radio>
          <el-radio value="class">类图</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="kind === 'class'" label="Package">
        <el-input v-model="pkg" placeholder="com.demo" style="width: 200px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="render">渲染</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-card v-loading="loading">
    <div ref="graphContainer" style="min-height: 400px; text-align: center"></div>
    <el-collapse style="margin-top: 16px">
      <el-collapse-item title="DOT 源码">
        <el-input :model-value="dotSource" type="textarea" :rows="10" readonly />
      </el-collapse-item>
    </el-collapse>
  </el-card>
</template>
