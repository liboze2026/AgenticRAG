<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { experimentsApi, type ExperimentRecord } from '../api/client'
import {
  AppCard, AppButton, AppTable, AppTag, AppDialog, AppDrawer, msg,
} from '../design/primitives'
import Icon from '../design/Icons.vue'

const records = ref<ExperimentRecord[]>([])
const loading = ref(false)
const selectedIds = ref<Set<number>>(new Set())
const showCompare = ref(false)
const detailOpen = ref(false)
const detailRow = ref<ExperimentRecord | null>(null)

const selectedRows = computed(() =>
  records.value.filter(r => selectedIds.value.has(r.id))
)

async function refresh() {
  loading.value = true
  try {
    const resp = await experimentsApi.listHistory()
    records.value = resp.data
  } catch {}
  loading.value = false
}

async function handleDelete(id: number) {
  if (!confirm(`确认注销实验记录 #${id}？`)) return
  await experimentsApi.deleteHistory(id)
  selectedIds.value.delete(id)
  await refresh()
  msg.success('已注销')
}

function toggleSelect(id: number) {
  if (selectedIds.value.has(id)) selectedIds.value.delete(id)
  else selectedIds.value.add(id)
  selectedIds.value = new Set(selectedIds.value)
}

function showDetail(row: ExperimentRecord) {
  detailRow.value = row
  detailOpen.value = true
}

function formatStrategy(v: any) {
  if (!v) return '—'
  if (typeof v === 'string') return v
  return v.name || JSON.stringify(v).slice(0, 30)
}

function formatTime(iso: string) {
  try {
    const d = new Date(iso)
    return `${d.getFullYear()}.${(d.getMonth()+1).toString().padStart(2,'0')}.${d.getDate().toString().padStart(2,'0')} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
  } catch { return iso }
}

const compareRows = computed(() => {
  if (selectedRows.value.length < 2) return []
  const rows: any[] = []
  rows.push({
    metric: 'MRR',
    ...Object.fromEntries(selectedRows.value.map(r => [`exp_${r.id}`, (r.metrics.mrr || 0).toFixed(4)])),
  })
  rows.push({
    metric: '查询数',
    ...Object.fromEntries(selectedRows.value.map(r => [`exp_${r.id}`, r.total_queries])),
  })
  const allKs = new Set<number>()
  selectedRows.value.forEach(r => Object.keys(r.metrics.recall_at_k || {}).forEach(k => allKs.add(Number(k))))
  for (const k of Array.from(allKs).sort((a, b) => a - b)) {
    rows.push({
      metric: `recall @ ${k}`,
      ...Object.fromEntries(selectedRows.value.map(r => [
        `exp_${r.id}`,
        ((r.metrics.recall_at_k || {})[k] || 0).toFixed(4)
      ])),
    })
  }
  rows.push({
    metric: '平均延迟 (ms)',
    ...Object.fromEntries(selectedRows.value.map(r => [
      `exp_${r.id}`,
      r.metrics.avg_timing_ms?.total_ms ? r.metrics.avg_timing_ms.total_ms.toFixed(0) : '—'
    ])),
  })
  return rows
})

const tableCols = [
  { key: 'sel', label: '选', width: '40px', align: 'center' as const },
  { key: 'id', label: '编号', width: '60px', numeric: true },
  { key: 'created_at', label: '记录时间', width: '160px' },
  { key: 'dataset_id', label: '集录', width: '70px' },
  { key: 'pipeline', label: '流水线' },
  { key: 'mrr', label: 'MRR', width: '90px', numeric: true },
  { key: 'recall', label: 'Recall@K', width: '220px' },
  { key: 'latency', label: '延迟', width: '90px', numeric: true },
  { key: 'queries', label: '问询', width: '60px', numeric: true },
  { key: 'note', label: '备注', width: '160px' },
  { key: 'ops', label: '操作', width: '140px', align: 'center' as const },
]

defineExpose({ refresh })
onMounted(refresh)
</script>

<template>
  <AppCard title="实 验 记 录" subtitle="evaluation history" :num="'EX'">
    <template #extra>
      <div class="eh__actions">
        <AppButton
          variant="ghost"
          size="sm"
          :disabled="selectedIds.size < 2"
          @click="showCompare = true"
        >
          <Icon name="filter" :size="13" />
          对比 ({{ selectedIds.size }})
        </AppButton>
        <AppButton variant="ghost" size="sm" :loading="loading" @click="refresh">
          <Icon name="reload" :size="13" />
          刷 新
        </AppButton>
      </div>
    </template>

    <AppTable
      :columns="tableCols"
      :rows="records"
      empty="尚无实验记录"
      :hover="false"
    >
      <template #cell-sel="{ row }">
        <input
          type="checkbox"
          :checked="selectedIds.has(row.id)"
          @change="toggleSelect(row.id)"
          class="eh__cb"
        />
      </template>
      <template #cell-id="{ row }">
        <span class="eh__id">№ {{ row.id }}</span>
      </template>
      <template #cell-created_at="{ row }">
        <span class="eh__time">{{ formatTime(row.created_at) }}</span>
      </template>
      <template #cell-dataset_id="{ row }">
        <AppTag v-if="row.dataset_id" size="sm" variant="blue"># {{ row.dataset_id }}</AppTag>
        <span v-else class="eh__dash">—</span>
      </template>
      <template #cell-pipeline="{ row }">
        <div class="eh__pl">
          <div><span class="eh__pl-l">检</span> {{ formatStrategy(row.pipeline_config?.yaml?.retriever || (row.pipeline_config as any)?.retriever) }}</div>
          <div><span class="eh__pl-l">生</span> {{ formatStrategy(row.pipeline_config?.yaml?.generator || (row.pipeline_config as any)?.generator) }}</div>
        </div>
      </template>
      <template #cell-mrr="{ row }">
        {{ (row.metrics.mrr || 0).toFixed(4) }}
      </template>
      <template #cell-recall="{ row }">
        <div class="eh__rc">
          <span v-for="(v, k) in row.metrics.recall_at_k" :key="k" class="eh__rc-item">
            @{{ k }}<b>{{ Number(v).toFixed(3) }}</b>
          </span>
        </div>
      </template>
      <template #cell-latency="{ row }">
        <span v-if="row.metrics.avg_timing_ms?.total_ms">
          {{ row.metrics.avg_timing_ms.total_ms.toFixed(0) }}<small> ms</small>
        </span>
        <span v-else class="eh__dash">—</span>
      </template>
      <template #cell-queries="{ row }">{{ row.total_queries }}</template>
      <template #cell-note="{ row }">
        <span class="eh__note" :title="row.note">{{ row.note || '—' }}</span>
      </template>
      <template #cell-ops="{ row }">
        <div class="eh__ops">
          <button class="eh__op-btn" @click="showDetail(row as ExperimentRecord)" title="详情">
            <Icon name="eye" :size="13" />
          </button>
          <button class="eh__op-btn eh__op-btn--del" @click="handleDelete(row.id)" title="注销">
            <Icon name="trash" :size="13" />
          </button>
        </div>
      </template>
    </AppTable>

    <!-- Detail Drawer -->
    <AppDrawer v-model="detailOpen" :title="`实验详情 · № ${detailRow?.id}`" width="780px">
      <div v-if="detailRow" class="eh-d">
        <section class="eh-d__sec">
          <h4 class="eh-d__title">流水线配置</h4>
          <pre class="eh-d__yaml">{{ JSON.stringify(detailRow.pipeline_config, null, 2) }}</pre>
        </section>

        <section class="eh-d__sec" v-if="detailRow.metrics.per_query?.length">
          <h4 class="eh-d__title">单 项 明 细</h4>
          <div class="eh-d__pq" v-for="(p, pi) in detailRow.metrics.per_query" :key="pi">
            <div class="eh-d__pq-q"><span class="eh-d__pq-no">{{ String(pi+1).padStart(2, '0') }}</span> {{ p.query }}</div>
            <div class="eh-d__pq-meta">
              <span>RR <b>{{ p.rr.toFixed(3) }}</b></span>
              <span>R@5 <b>{{ (p.recall_at_k[5] || 0).toFixed(3) }}</b></span>
              <span v-if="p.timing_ms?.total_ms">耗时 <b>{{ p.timing_ms.total_ms.toFixed(0) }}<small> ms</small></b></span>
            </div>
            <div class="eh-d__pq-rel">期望: <code>{{ p.relevant.join(', ') }}</code></div>
            <div class="eh-d__pq-ret">召回: <code>{{ p.retrieved.slice(0, 5).join(', ') }}{{ p.retrieved.length > 5 ? '⋯' : '' }}</code></div>
          </div>
        </section>
      </div>
    </AppDrawer>

    <!-- Compare Dialog -->
    <AppDialog v-model="showCompare" title="实 验 对 比" width="900px">
      <div v-if="selectedRows.length >= 2" class="eh-c">
        <table class="eh-c__tbl">
          <thead>
            <tr>
              <th class="eh-c__th-l">指标 / 配置</th>
              <th v-for="r in selectedRows" :key="r.id">
                <div class="eh-c__h">
                  <span class="eh-c__h-id">№ {{ r.id }}</span>
                  <span class="eh-c__h-note" v-if="r.note">{{ r.note }}</span>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in compareRows" :key="ri">
              <td class="eh-c__l">{{ row.metric }}</td>
              <td v-for="r in selectedRows" :key="r.id" class="eh-c__v">{{ row[`exp_${r.id}`] }}</td>
            </tr>
          </tbody>
        </table>

        <h5 class="eh-c__yt">配 置 差 异</h5>
        <div class="eh-c__yamls">
          <div v-for="r in selectedRows" :key="r.id" class="eh-c__y-card">
            <div class="eh-c__y-head">№ {{ r.id }}</div>
            <pre class="eh-c__yaml">{{ JSON.stringify(r.pipeline_config, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </AppDialog>
  </AppCard>
</template>

<style scoped>
.eh__actions { display: flex; gap: 6px; }
.eh__id, .eh__time {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.eh__dash { color: var(--ink-mute); }

.eh__cb {
  width: 14px; height: 14px;
  accent-color: var(--red);
}

.eh__pl { font-size: var(--fz-mono-sm); line-height: 1.5; font-family: var(--mono); }
.eh__pl-l {
  display: inline-block;
  width: 18px; height: 18px;
  text-align: center;
  background: var(--blue);
  color: var(--paper);
  font-family: var(--serif);
  font-weight: 700;
  font-size: 11px;
  line-height: 18px;
  margin-right: 6px;
}

.eh__rc { display: flex; flex-wrap: wrap; gap: 8px; font-family: var(--mono); font-size: 11px; }
.eh__rc-item { color: var(--ink-mute); font-variant-numeric: tabular-nums; }
.eh__rc-item b { color: var(--blue); margin-left: 4px; font-weight: 700; }

.eh__note {
  font-family: var(--serif);
  font-style: italic;
  color: var(--ink-soft);
  font-size: var(--fz-sm);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.eh__ops { display: flex; gap: 4px; justify-content: center; }
.eh__op-btn {
  width: 28px; height: 28px;
  background: transparent;
  border: 1px solid var(--rule);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--ink-mute);
  transition: all var(--dur-fast);
}
.eh__op-btn:hover { color: var(--blue); border-color: var(--blue); background: var(--paper-deep); }
.eh__op-btn--del:hover { color: var(--red); border-color: var(--red); }

/* Detail drawer */
.eh-d { display: flex; flex-direction: column; gap: var(--gap-5); }
.eh-d__sec {}
.eh-d__title {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--blue);
  letter-spacing: 0.18em;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 6px;
  margin: 0 0 12px;
}
.eh-d__yaml {
  font-family: var(--mono);
  font-size: 11px;
  background: var(--paper-deep);
  border: 1px solid var(--rule);
  padding: 12px 14px;
  max-height: 280px;
  overflow: auto;
  margin: 0;
  line-height: 1.6;
  color: var(--ink);
}

.eh-d__pq {
  border-left: 3px solid var(--blue);
  padding: 10px 14px;
  margin-bottom: 10px;
  background: var(--paper-deep);
}
.eh-d__pq-q {
  font-family: var(--serif);
  font-weight: 600;
  font-size: var(--fz-base);
  color: var(--ink);
  margin-bottom: 6px;
}
.eh-d__pq-no {
  font-family: var(--mono);
  font-weight: 700;
  color: var(--red);
  margin-right: 8px;
}
.eh-d__pq-meta {
  display: flex;
  gap: var(--gap-4);
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  margin-bottom: 6px;
  letter-spacing: 0.05em;
}
.eh-d__pq-meta b {
  color: var(--blue);
  margin-left: 4px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.eh-d__pq-meta b small { font-weight: 400; color: var(--ink-mute); }
.eh-d__pq-rel, .eh-d__pq-ret {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink-soft);
  margin-top: 2px;
}
.eh-d__pq-rel code, .eh-d__pq-ret code {
  background: var(--paper);
  padding: 1px 4px;
  border: 1px solid var(--rule-fine);
  font-size: 10px;
  color: var(--ink);
}

/* Compare */
.eh-c__tbl {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--serif);
  margin-bottom: var(--gap-5);
}
.eh-c__tbl th {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  text-transform: uppercase;
  letter-spacing: var(--ls-medium);
  color: var(--ink-mute);
  text-align: left;
  padding: 8px 12px;
  border-top: 2px solid var(--ink);
  border-bottom: 1px solid var(--ink);
  background: var(--paper-deep);
}
.eh-c__th-l { width: 160px; }
.eh-c__h { display: flex; flex-direction: column; }
.eh-c__h-id {
  font-family: var(--mono);
  font-weight: 700;
  color: var(--blue);
  font-size: var(--fz-sm);
}
.eh-c__h-note {
  font-family: var(--serif);
  font-style: italic;
  color: var(--ink-soft);
  font-size: 11px;
  text-transform: none;
  letter-spacing: normal;
  margin-top: 2px;
}
.eh-c__tbl td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--rule-fine);
  font-size: var(--fz-sm);
}
.eh-c__l { color: var(--ink-soft); font-weight: 600; }
.eh-c__v {
  font-family: var(--mono);
  font-weight: 700;
  color: var(--blue);
  font-variant-numeric: tabular-nums;
}

.eh-c__yt {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--blue);
  letter-spacing: 0.18em;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 4px;
  margin: var(--gap-5) 0 var(--gap-3);
}
.eh-c__yamls {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--gap-3);
}
.eh-c__y-card { border: 1px solid var(--rule); }
.eh-c__y-head {
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono-sm);
  color: var(--blue);
  background: var(--paper-deep);
  border-bottom: 1px solid var(--rule);
  padding: 6px 10px;
  letter-spacing: 0.1em;
}
.eh-c__yaml {
  font-family: var(--mono);
  font-size: 10px;
  padding: 8px 10px;
  margin: 0;
  max-height: 240px;
  overflow: auto;
  line-height: 1.5;
  color: var(--ink);
}
</style>
