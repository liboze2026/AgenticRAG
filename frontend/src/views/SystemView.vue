<template>
  <div>
    <h2>系统状态</h2>
    <el-button @click="refresh" :loading="loading" style="margin-bottom: 16px">刷新</el-button>
    <el-descriptions v-if="health" :column="1" border>
      <el-descriptions-item label="系统状态">
        <el-tag :type="health.status === 'ok' ? 'success' : 'danger'">{{ health.status }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="Worker 状态">
        <el-tag :type="health.worker?.status === 'ok' ? 'success' : 'danger'">{{ health.worker?.status || 'unknown' }}</el-tag>
        <span v-if="health.worker?.model" style="margin-left: 8px">模型: {{ health.worker.model }}</span>
      </el-descriptions-item>
      <el-descriptions-item label="Qdrant 状态">
        <el-tag :type="health.qdrant?.status === 'ok' ? 'success' : 'danger'">{{ health.qdrant?.status || 'unknown' }}</el-tag>
      </el-descriptions-item>
    </el-descriptions>

    <el-card style="margin-top: 16px" v-if="cacheStats">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>缓存状态</span>
          <el-button size="small" @click="loadCacheStats">刷新</el-button>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="Query 缓存">
          <el-tag :type="cacheStats.query_cache.enabled ? 'success' : 'info'">
            {{ cacheStats.query_cache.enabled ? '已启用' : '已禁用' }}
          </el-tag>
          条目: {{ cacheStats.query_cache.entries }} ·
          大小: {{ formatBytes(cacheStats.query_cache.size_bytes) }}
        </el-descriptions-item>
        <el-descriptions-item label="Generation 缓存">
          <el-tag :type="cacheStats.generation_cache.enabled ? 'success' : 'info'">
            {{ cacheStats.generation_cache.enabled ? '已启用' : '已禁用' }}
          </el-tag>
          条目: {{ cacheStats.generation_cache.entries }} ·
          大小: {{ formatBytes(cacheStats.generation_cache.size_bytes) }}
        </el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 12px">
        <el-button type="warning" size="small" @click="clearQueryCache">清空 Query 缓存</el-button>
        <el-button type="warning" size="small" @click="clearGenCache">清空 Generation 缓存</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { systemApi, cacheApi } from '../api/client'
import { ElMessage } from 'element-plus'

const health = ref<any>(null)
const cacheStats = ref<any>(null)
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    const resp = await systemApi.health()
    health.value = resp.data
    await loadCacheStats()
  } finally { loading.value = false }
}

async function loadCacheStats() {
  try {
    const resp = await cacheApi.stats()
    cacheStats.value = resp.data
  } catch {}
}

async function clearQueryCache() {
  await cacheApi.clearQuery()
  ElMessage.success('Query 缓存已清空')
  await loadCacheStats()
}

async function clearGenCache() {
  await cacheApi.clearGeneration()
  ElMessage.success('Generation 缓存已清空')
  await loadCacheStats()
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(2)} MB`
}

onMounted(refresh)
</script>
