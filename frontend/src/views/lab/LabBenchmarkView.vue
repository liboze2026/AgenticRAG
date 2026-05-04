<script setup lang="ts">
import { ref, computed } from 'vue'
import { AppPageHead, AppCard, AppButton, AppTag } from '../../design/primitives'
import { labApi, type BenchmarkResponse, type BenchmarkQueryItem } from '../../api/client'

const SAMPLE = `[
  {
    "query": "示例：图1中研发投入是多少？",
    "relevant_pages": [
      {"document_id": "REPLACE_WITH_DOC_ID", "page_number": 5}
    ]
  }
]`

const queriesText = ref(SAMPLE)
const channelColpali = ref(true)
const channelBm25 = ref(true)
const channelRrf = ref(true)
const topK = ref(10)
const timeoutSec = ref(30)
const loading = ref(false)
const data = ref<BenchmarkResponse | null>(null)
const error = ref('')

const channels = computed(() => {
  const out: string[] = []
  if (channelColpali.value) out.push('colpali')
  if (channelBm25.value) out.push('bm25')
  if (channelRrf.value) out.push('rrf')
  return out
})

async function run() {
  error.value = ''
  let parsed: BenchmarkQueryItem[]
  try {
    parsed = JSON.parse(queriesText.value)
    if (!Array.isArray(parsed)) throw new Error('expected JSON array')
    for (const item of parsed) {
      if (!item.query || !Array.isArray(item.relevant_pages)) {
        throw new Error('每项需有 query 与 relevant_pages 数组')
      }
    }
  } catch (e: any) {
    error.value = `JSON 解析失败: ${e.message}`
    return
  }
  if (!parsed.length) {
    error.value = '请至少提供一个 query'
    return
  }
  if (!channels.value.length) {
    error.value = '请至少选择一个通道'
    return
  }

  loading.value = true
  data.value = null
  try {
    const r = await labApi.benchmark(parsed, {
      channels: channels.value, topK: topK.value, timeoutSec: timeoutSec.value,
    })
    data.value = r.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}

function downloadJson() {
  if (!data.value) return
  const blob = new Blob([JSON.stringify(data.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `benchmark_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function pct(v: number) { return (v * 100).toFixed(1) + '%' }
</script>

<template>
  <div class="bm">
    <AppPageHead
      chapter="H"
      kicker="LAB · Phase 9"
      title="基准评测"
      subtitle="对一批 query+ground-truth 跑 colpali / bm25 / rrf 通道，比较 MRR / Recall@K / Hit@1"
      :meta="[
        { label: '入口', value: 'POST /api/lab/benchmark' },
        { label: '上限', value: '单次 ≤ 200 个 query' },
      ]"
      stamp="LAB&#10;评测"
    />

    <AppCard class="bm__form">
      <h3>查询集 (JSON)</h3>
      <p class="bm__hint">每项 <code>{ query, relevant_pages: [{document_id, page_number}, ...] }</code>，相关页用作 ground-truth</p>
      <textarea v-model="queriesText" class="bm__ta" rows="10"></textarea>
      <div class="bm__row">
        <label class="bm__chk"><input type="checkbox" v-model="channelColpali" /> colpali (主管道)</label>
        <label class="bm__chk"><input type="checkbox" v-model="channelBm25" /> bm25 (Lab 文本)</label>
        <label class="bm__chk"><input type="checkbox" v-model="channelRrf" /> rrf (融合)</label>
        <label class="bm__num"><span>top-k</span><input type="number" v-model.number="topK" min="1" max="50" /></label>
        <label class="bm__num"><span>超时秒</span><input type="number" v-model.number="timeoutSec" min="1" max="120" /></label>
        <AppButton variant="primary" :loading="loading" @click="run">开始评测</AppButton>
        <AppButton v-if="data" @click="downloadJson">下载 JSON</AppButton>
      </div>
      <p v-if="error" class="bm__err">{{ error }}</p>
    </AppCard>

    <AppCard v-if="data" class="bm__metrics">
      <h3>聚合指标</h3>
      <table>
        <thead>
          <tr>
            <th>通道</th><th>查询数</th><th>MRR</th><th>Recall@5</th><th>Recall@10</th><th>Hit@1</th><th>平均耗时</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in data.metrics" :key="m.channel">
            <td><AppTag size="sm" variant="blue">{{ m.channel }}</AppTag></td>
            <td>{{ m.queries }}</td>
            <td>{{ m.mrr.toFixed(3) }}</td>
            <td>{{ pct(m.recall_at_5) }}</td>
            <td>{{ pct(m.recall_at_10) }}</td>
            <td>{{ pct(m.hit_at_1) }}</td>
            <td class="bm__lat">{{ m.avg_latency_ms.toFixed(0) }} ms</td>
          </tr>
        </tbody>
      </table>
      <p v-if="data.note" class="bm__note">{{ data.note }}</p>
    </AppCard>

    <AppCard v-if="data && data.per_query.length" class="bm__detail">
      <h3>逐 query 详情</h3>
      <table>
        <thead>
          <tr><th>查询</th><th>通道</th><th>RR</th><th>R@5</th><th>R@10</th><th>Hit@1</th><th>命中</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr v-for="(p, i) in data.per_query" :key="i" :class="{ 'bm__row--zero': p.rr === 0 && !p.note }">
            <td class="bm__q">{{ p.query.length > 40 ? p.query.slice(0, 40) + '…' : p.query }}</td>
            <td>{{ p.channel }}</td>
            <td>{{ p.rr.toFixed(2) }}</td>
            <td>{{ pct(p.recall_at_5) }}</td>
            <td>{{ pct(p.recall_at_10) }}</td>
            <td>{{ pct(p.hit_at_1) }}</td>
            <td class="bm__hits">{{ p.retrieved.length }}/{{ p.relevant.length }}</td>
            <td class="bm__cell-note">{{ p.note }}</td>
          </tr>
        </tbody>
      </table>
    </AppCard>
  </div>
</template>

<style scoped>
.bm { max-width: 1200px; margin: 0 auto; }

.bm__form { padding: var(--gap-4); margin-bottom: var(--gap-3); }
.bm__form h3 { margin: 0 0 6px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.bm__hint { margin: 0 0 8px; font-family: var(--serif); font-size: var(--fz-sm); color: var(--ink-soft); }
.bm__hint code { font-family: var(--mono); background: var(--paper-deep); padding: 1px 4px; }
.bm__ta { width: 100%; padding: 10px; font-family: var(--mono); font-size: var(--fz-mono-sm); border: 1px solid var(--rule); background: var(--paper); resize: vertical; }
.bm__ta:focus { outline: 2px solid var(--blue); }
.bm__row { display: flex; align-items: center; gap: var(--gap-3); flex-wrap: wrap; margin-top: 12px; }
.bm__chk { display: flex; align-items: center; gap: 6px; font-family: var(--serif); font-size: var(--fz-sm); color: var(--ink-soft); }
.bm__num { display: flex; align-items: center; gap: 6px; font-family: var(--serif); font-size: var(--fz-sm); color: var(--ink-soft); }
.bm__num input { width: 60px; padding: 6px 8px; border: 1px solid var(--rule); font-family: var(--mono); }
.bm__err { margin: 8px 0 0; color: var(--red); font-family: var(--mono); font-size: var(--fz-mono-sm); }

.bm__metrics, .bm__detail { padding: var(--gap-4); margin-bottom: var(--gap-3); }
.bm__metrics h3, .bm__detail h3 { margin: 0 0 12px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.bm__metrics table, .bm__detail table { width: 100%; border-collapse: collapse; font-family: var(--serif); font-size: var(--fz-sm); }
.bm__metrics th, .bm__metrics td, .bm__detail th, .bm__detail td {
  padding: 8px 10px; border-bottom: 1px dotted var(--rule); text-align: left; vertical-align: top;
}
.bm__metrics th, .bm__detail th { font-weight: 700; color: var(--ink-mute); letter-spacing: 0.1em; font-size: 11px; }
.bm__lat { font-family: var(--mono); color: var(--ink-soft); }
.bm__q { color: var(--ink); }
.bm__hits { font-family: var(--mono); }
.bm__cell-note { color: var(--ink-soft); font-size: var(--fz-sm); }
.bm__row--zero { color: var(--ink-mute); }
.bm__note { margin: 12px 0 0; font-family: var(--serif); color: var(--ink-soft); font-size: var(--fz-sm); }
</style>
