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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { systemApi } from '../api/client'

const health = ref<any>(null)
const loading = ref(false)

async function refresh() {
  loading.value = true
  try { const resp = await systemApi.health(); health.value = resp.data }
  finally { loading.value = false }
}

onMounted(refresh)
</script>
