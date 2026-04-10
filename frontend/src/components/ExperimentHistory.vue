<template>
  <el-card style="margin-top: 16px">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>实验历史</span>
        <div>
          <el-button size="small" :disabled="selectedRows.length < 2" @click="showCompare = true">
            对比 ({{ selectedRows.length }})
          </el-button>
          <el-button size="small" @click="refresh" :loading="loading">刷新</el-button>
        </div>
      </div>
    </template>
    <el-table :data="records" stripe @selection-change="onSelectionChange">
      <el-table-column type="selection" width="50" />
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column label="数据集" width="80">
        <template #default="{ row }">
          <span v-if="row.dataset_id">#{{ row.dataset_id }}</span>
          <span v-else style="color: #999">—</span>
        </template>
      </el-table-column>
      <el-table-column label="Pipeline" width="200">
        <template #default="{ row }">
          <div style="font-size: 12px">
            <div>检索: {{ formatStrategy(row.pipeline_config?.yaml?.retriever || row.pipeline_config?.retriever) }}</div>
            <div>生成: {{ formatStrategy(row.pipeline_config?.yaml?.generator || row.pipeline_config?.generator) }}</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="MRR" width="90">
        <template #default="{ row }">
          {{ (row.metrics.mrr || 0).toFixed(4) }}
        </template>
      </el-table-column>
      <el-table-column label="Recall@K" width="220">
        <template #default="{ row }">
          <span v-for="(v, k) in row.metrics.recall_at_k" :key="k" style="margin-right: 8px; font-size: 12px">
            @{{ k }}: {{ Number(v).toFixed(3) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="平均延迟" width="110">
        <template #default="{ row }">
          <span v-if="row.metrics.avg_timing_ms?.total_ms">
            {{ row.metrics.avg_timing_ms.total_ms.toFixed(0) }} ms
          </span>
          <span v-else style="color: #999">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="total_queries" label="查询" width="60" />
      <el-table-column prop="note" label="备注" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" @click="showDetail(row)">详情</el-button>
          <el-button type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Detail dialog: per-query drill-down -->
    <el-dialog v-model="showDetailDialog" title="实验详情" width="80%" top="5vh">
      <div v-if="detailRow">
        <h4>Pipeline 配置</h4>
        <pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; font-size: 12px; max-height: 200px; overflow: auto">{{ JSON.stringify(detailRow.pipeline_config, null, 2) }}</pre>

        <h4 style="margin-top: 16px">每查询明细</h4>
        <el-table :data="detailRow.metrics.per_query || []" stripe size="small">
          <el-table-column label="Query" min-width="200">
            <template #default="{ row }">{{ row.query }}</template>
          </el-table-column>
          <el-table-column label="Relevant" width="160">
            <template #default="{ row }">
              <div style="font-size: 11px">{{ row.relevant.join(', ') }}</div>
            </template>
          </el-table-column>
          <el-table-column label="Top Retrieved" width="200">
            <template #default="{ row }">
              <div style="font-size: 11px">{{ row.retrieved.slice(0, 5).join(', ') }}</div>
            </template>
          </el-table-column>
          <el-table-column label="RR" width="80">
            <template #default="{ row }">{{ row.rr.toFixed(3) }}</template>
          </el-table-column>
          <el-table-column label="R@5" width="80">
            <template #default="{ row }">{{ (row.recall_at_k[5] || 0).toFixed(3) }}</template>
          </el-table-column>
          <el-table-column label="耗时" width="80">
            <template #default="{ row }">
              <span v-if="row.timing_ms?.total_ms">{{ row.timing_ms.total_ms.toFixed(0) }} ms</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <!-- Compare dialog -->
    <el-dialog v-model="showCompare" title="实验对比" width="90%" top="5vh">
      <div v-if="selectedRows.length >= 2">
        <h4>指标对比</h4>
        <el-table :data="compareMetricsRows" stripe>
          <el-table-column prop="metric" label="指标" width="160" />
          <el-table-column v-for="r in selectedRows" :key="r.id" :label="`#${r.id}${r.note ? ' (' + r.note + ')' : ''}`">
            <template #default="{ row }">{{ row[`exp_${r.id}`] }}</template>
          </el-table-column>
        </el-table>

        <h4 style="margin-top: 16px">配置 diff</h4>
        <el-row :gutter="12">
          <el-col v-for="r in selectedRows" :key="r.id" :span="Math.floor(24 / selectedRows.length)">
            <el-card>
              <template #header>#{{ r.id }} {{ r.note ? '(' + r.note + ')' : '' }}</template>
              <pre style="font-size: 11px; max-height: 400px; overflow: auto">{{ JSON.stringify(r.pipeline_config, null, 2) }}</pre>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { experimentsApi, type ExperimentRecord } from '../api/client'

const records = ref<ExperimentRecord[]>([])
const loading = ref(false)
const selectedRows = ref<ExperimentRecord[]>([])
const showCompare = ref(false)
const showDetailDialog = ref(false)
const detailRow = ref<ExperimentRecord | null>(null)

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

function showDetail(row: ExperimentRecord) {
  detailRow.value = row
  showDetailDialog.value = true
}

function onSelectionChange(rows: ExperimentRecord[]) {
  selectedRows.value = rows
}

function formatStrategy(v: any) {
  if (!v) return '-'
  if (typeof v === 'string') return v
  return v.name || JSON.stringify(v).slice(0, 30)
}

const compareMetricsRows = computed(() => {
  const rows: any[] = []
  // MRR
  rows.push({
    metric: 'MRR',
    ...Object.fromEntries(selectedRows.value.map(r => [`exp_${r.id}`, (r.metrics.mrr || 0).toFixed(4)])),
  })
  // Total queries
  rows.push({
    metric: 'Total Queries',
    ...Object.fromEntries(selectedRows.value.map(r => [`exp_${r.id}`, r.total_queries])),
  })
  // Recall@K — collect all K values
  const allKs = new Set<number>()
  selectedRows.value.forEach(r => {
    Object.keys(r.metrics.recall_at_k || {}).forEach(k => allKs.add(Number(k)))
  })
  for (const k of Array.from(allKs).sort((a, b) => a - b)) {
    rows.push({
      metric: `Recall@${k}`,
      ...Object.fromEntries(selectedRows.value.map(r => [
        `exp_${r.id}`,
        ((r.metrics.recall_at_k || {})[k] || 0).toFixed(4)
      ])),
    })
  }
  // Avg latency
  rows.push({
    metric: 'Avg Latency (ms)',
    ...Object.fromEntries(selectedRows.value.map(r => [
      `exp_${r.id}`,
      r.metrics.avg_timing_ms?.total_ms ? r.metrics.avg_timing_ms.total_ms.toFixed(0) : '—'
    ])),
  })
  return rows
})

defineExpose({ refresh })
onMounted(refresh)
</script>
