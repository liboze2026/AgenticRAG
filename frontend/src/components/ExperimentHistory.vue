<template>
  <el-card style="margin-top: 16px">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>实验历史</span>
        <el-button size="small" @click="refresh" :loading="loading">刷新</el-button>
      </div>
    </template>
    <el-table :data="records" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column label="Pipeline" width="220">
        <template #default="{ row }">
          <div style="font-size: 12px">
            <div>检索: {{ formatStrategy(row.pipeline_config.retriever) }}</div>
            <div>生成: {{ formatStrategy(row.pipeline_config.generator) }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="MRR" width="100">
        <template #default="{ row }">
          {{ (row.metrics.mrr || 0).toFixed(4) }}
        </template>
      </el-table-column>
      <el-table-column label="Recall@K">
        <template #default="{ row }">
          <span v-for="(v, k) in row.metrics.recall_at_k" :key="k" style="margin-right: 12px">
            @{{ k }}: {{ v.toFixed(3) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="total_queries" label="查询数" width="80" />
      <el-table-column prop="note" label="备注" />
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { experimentsApi, type ExperimentRecord } from '../api/client'

const records = ref<ExperimentRecord[]>([])
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    const resp = await experimentsApi.listHistory()
    records.value = resp.data
  } finally { loading.value = false }
}

async function handleDelete(id: number) {
  await experimentsApi.deleteHistory(id)
  await refresh()
}

function formatStrategy(v: any) {
  if (!v) return '-'
  if (typeof v === 'string') return v
  return v.name || '-'
}

defineExpose({ refresh })
onMounted(refresh)
</script>
