<script setup lang="ts">
import { computed } from 'vue'
import type { EvalMetrics } from '../api/client'
import { AppMetricGrid, AppCard } from '../design/primitives'

const props = defineProps<{ metrics: EvalMetrics | null }>()

const cells = computed(() => {
  if (!props.metrics) return []
  const m = props.metrics
  const recall = m.recall_at_k || {}
  const ks = Object.keys(recall).map(Number).sort((a, b) => a - b)
  const out: { label: string; value: string; unit?: string }[] = [
    { label: 'MRR', value: (m.mrr || 0).toFixed(4) },
    { label: '查询数', value: String(m.total_queries), unit: '次' },
  ]
  for (const k of ks) {
    out.push({ label: `Recall@${k}`, value: (recall[k] || 0).toFixed(4) })
  }
  if (m.avg_timing_ms?.total_ms) {
    out.push({ label: '平均延迟', value: m.avg_timing_ms.total_ms.toFixed(0), unit: 'ms' })
  }
  return out
})
</script>

<template>
  <AppCard v-if="metrics" title="评测结果" subtitle="evaluation result" :num="'EV'">
    <AppMetricGrid :metrics="cells" :cols="Math.min(cells.length, 4)" />
  </AppCard>
</template>
