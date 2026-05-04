<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { AppPageHead, AppCard, AppButton, AppTag, msg } from '../../design/primitives'
import LabQueryBar from '../../components/lab/LabQueryBar.vue'
import { labApi, documentsApi, type RegionResponse, type RegionHit, type DocumentInfo } from '../../api/client'

const loading = ref(false)
const indexing = ref(false)
const data = ref<RegionResponse | null>(null)
const error = ref('')
const docs = ref<DocumentInfo[]>([])
// jobs: doc_id -> {state, indexed, current_page, total_pages, ...}
const jobs = ref<Record<string, any>>({})
let pollTimer: number | null = null

async function refreshDocs() {
  try {
    const resp = await documentsApi.list()
    docs.value = resp.data.filter(d => d.status === 'completed')
  } catch { /* swallow */ }
}

async function refreshJobs() {
  try {
    const resp = await labApi.regionJobs()
    jobs.value = resp.data
  } catch { /* swallow */ }
}

function startPolling() {
  if (pollTimer !== null) return
  pollTimer = window.setInterval(refreshJobs, 2000)
}
function stopPollingIfIdle() {
  const anyRunning = Object.values(jobs.value).some((j: any) => j.state === 'running' || j.state === 'pending')
  if (!anyRunning && pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  await Promise.all([refreshDocs(), refreshJobs()])
  if (Object.values(jobs.value).some((j: any) => j.state === 'running' || j.state === 'pending')) {
    startPolling()
  }
})
onBeforeUnmount(() => {
  if (pollTimer !== null) window.clearInterval(pollTimer)
})

async function run(payload: { query: string; topK: number }) {
  loading.value = true
  data.value = null
  error.value = ''
  try {
    const resp = await labApi.regionQuery(payload.query, payload.topK)
    data.value = resp.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}

async function indexAll() {
  indexing.value = true
  try {
    const resp = await labApi.regionIndexAll()           // async by default
    msg.success(resp.data.note)
    startPolling()
    await refreshJobs()
  } catch (e: any) {
    msg.error(e?.response?.data?.detail || e?.message || '索引失败')
  } finally {
    indexing.value = false
  }
}

async function indexOne(docId: string) {
  try {
    const resp = await labApi.regionIndexOne(docId)       // async by default
    msg.success(resp.data.note)
    startPolling()
    await refreshJobs()
  } catch (e: any) {
    msg.error(e?.response?.data?.detail || e?.message || '索引失败')
  }
}

function jobLine(docId: string): string {
  const j = jobs.value[docId]
  if (!j) return ''
  if (j.state === 'pending') return '等待中…'
  if (j.state === 'running') {
    const cur = j.current_page ?? 0, tot = j.total_pages ?? 0
    return `处理中 ${cur}/${tot} · 已入库 ${j.indexed ?? 0} 区域`
  }
  if (j.state === 'completed') return j.note || `已完成 (${j.indexed ?? 0} 区域)`
  if (j.state === 'failed') return `失败: ${j.note ?? ''}`
  return j.state
}
function jobState(docId: string): string {
  return jobs.value[docId]?.state ?? ''
}

// stop polling when no active jobs
import { watch } from 'vue'
watch(jobs, () => stopPollingIfIdle(), { deep: true })

function regionImg(hit: RegionHit) {
  return `/api/images/${hit.document_id}/page_${hit.page_number}.png`
}
function shortId(id: string) {
  return id.length > 16 ? id.slice(0, 8) + '⋯' + id.slice(-3) : id
}
function elementLabel(t: string) {
  return ({ text_block: '正文', heading: '标题', table: '表格', figure: '图表' } as Record<string, string>)[t] || t
}
// Compute hit thumb crop CSS using bbox / page natural dimensions.
// We don't know the natural page size on hit alone (only bbox), but the image
// element + object-fit:cover already centers; we simulate "crop to bbox" via
// background-image + background-position calculated on load.
function bboxClip(hit: RegionHit) {
  // We rely on the page image natural size matching layout coords (DPI=200).
  // Use clip-path to confine the visible area to the bbox.
  const { x0, y0, x1, y1 } = hit.bbox
  return {
    backgroundImage: `url(${regionImg(hit)})`,
    backgroundSize: 'auto',
    backgroundPosition: `-${x0}px -${y0}px`,
    width: `${Math.max(64, x1 - x0)}px`,
    height: `${Math.max(48, y1 - y0)}px`,
    maxWidth: '100%',
  }
}
</script>

<template>
  <div class="lr">
    <AppPageHead
      chapter="D"
      kicker="LAB · 方法对比"
      title="区域级检索 (Layout-level)"
      subtitle="按 LayoutElement 粒度独立索引和检索：直接命中具体的文本块/表格/图表区域，而非整页"
      :meta="[
        { label: '入口', value: '/api/lab/region/query' },
        { label: '基线', value: '页级检索 (主 pipeline)' },
      ]"
      stamp="区域&#10;检索"
    />

    <AppCard class="lr__bar">
      <LabQueryBar
        :loading="loading"
        placeholder="试一试: '论文中第一个表格的 NDCG 列', '展示 Recall 趋势的图'"
        button-label="区域检索"
        @submit="run"
      />
    </AppCard>

    <AppCard class="lr__index">
      <header class="lr__index-h">
        <h4>索引控制</h4>
        <span class="lr__hint-mini">区域索引会裁剪每页 LayoutElement 单独建库</span>
      </header>
      <div class="lr__index-row">
        <AppButton variant="primary" :loading="indexing" @click="indexAll">索引所有文档区域</AppButton>
        <AppButton variant="ghost" @click="refreshDocs">刷新文档列表</AppButton>
      </div>
      <ul v-if="docs.length" class="lr__doc-list">
        <li v-for="d in docs" :key="d.id" class="lr__doc"
            :data-state="jobState(d.id)">
          <span class="lr__doc-name" :title="d.id">{{ d.filename || shortId(d.id) }}</span>
          <span class="lr__doc-pages">{{ d.total_pages }} 页</span>
          <span v-if="jobLine(d.id)" class="lr__doc-job">{{ jobLine(d.id) }}</span>
          <AppButton size="sm" variant="ghost"
            :disabled="indexing || jobState(d.id) === 'running' || jobState(d.id) === 'pending'"
            @click="indexOne(d.id)">索引此文档</AppButton>
        </li>
      </ul>
      <div v-else class="lr__doc-empty">尚未发现已完成索引的文档 — 请先在 [文档管理] 上传 PDF</div>
    </AppCard>

    <div v-if="error" class="lr__err">{{ error }}</div>

    <section v-if="data?.note" class="lr__note">{{ data.note }}</section>

    <section v-if="data?.hits.length" class="lr__hits">
      <h4 class="lr__hits-h">区域命中 ({{ data.hits.length }})</h4>
      <div class="lr__grid">
        <article v-for="(hit, i) in data.hits" :key="i" class="lr__card" :data-type="hit.element_type">
          <header class="lr__card-h">
            <span class="lr__rank">{{ i + 1 }}</span>
            <AppTag :variant="hit.element_type === 'figure' ? 'red' : 'paper'" size="sm">
              {{ elementLabel(hit.element_type) }}
            </AppTag>
            <span class="lr__score">{{ hit.score.toFixed(3) }}</span>
          </header>
          <div class="lr__crop-wrap">
            <div class="lr__crop" :style="bboxClip(hit)" :title="`bbox: ${hit.bbox.x0.toFixed(0)},${hit.bbox.y0.toFixed(0)} - ${hit.bbox.x1.toFixed(0)},${hit.bbox.y1.toFixed(0)}`">
            </div>
          </div>
          <div class="lr__card-meta">
            <div><span class="lr__ml">页</span><span class="lr__mv">第 {{ hit.page_number }} 页</span></div>
            <div><span class="lr__ml">索引</span><span class="lr__mv lr__mv--mono">#{{ hit.element_index }}</span></div>
            <div :title="hit.document_id"><span class="lr__ml">文档</span><span class="lr__mv lr__mv--mono">{{ shortId(hit.document_id) }}</span></div>
          </div>
          <p v-if="hit.text" class="lr__quote">{{ hit.text.slice(0, 220) }}{{ hit.text.length > 220 ? '⋯' : '' }}</p>
          <p v-else-if="hit.element_type === 'figure'" class="lr__quote lr__quote--soft">（图像区域 · 视觉嵌入命中）</p>
        </article>
      </div>
    </section>

    <AppCard v-if="!data && !loading" class="lr__hint">
      <h4>这一页演示了什么？</h4>
      <p>
        主 pipeline 的 ColPali 索引粒度是「页」 — 命中一页后用户得自己在页里找证据。
        <b>区域级检索</b> 把每个 LayoutElement (文本块/表格/图表) 单独裁剪、单独编码、单独建库，
        查询时直接定位到具体区域。MMDocIR 论文证明 layout-level 比 page-level 更细粒度有效。
      </p>
      <p class="lr__hint-cite">对应开题报告 §3.1.1 三级结构化表示 + 文献 [5] MMDocIR layout-level retrieval</p>
      <p class="lr__hint-warn">
        ⚠ 区域索引需要把每个元素单独发到 worker 编码，比页级慢得多。建议先用「仅索引此文档」单测一篇 PDF。
      </p>
    </AppCard>
  </div>
</template>

<style scoped>
.lr { max-width: 1200px; margin: 0 auto; }
.lr__bar { padding: var(--gap-4); margin-bottom: var(--gap-3); }

.lr__index { padding: var(--gap-4); margin-bottom: var(--gap-4); }
.lr__index-h {
  display: flex; align-items: baseline; gap: 12px;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 6px; margin-bottom: 10px;
}
.lr__index-h h4 {
  margin: 0; font-family: var(--serif); color: var(--blue);
  letter-spacing: 0.18em; font-size: var(--fz-h4);
}
.lr__hint-mini {
  font-family: var(--mono); font-size: var(--fz-mono-sm);
  color: var(--ink-mute); letter-spacing: 0.05em;
}
.lr__index-row { display: flex; gap: 8px; margin-bottom: 12px; }

.lr__doc-list { list-style: none; padding: 0; margin: 0; }
.lr__doc {
  display: grid; grid-template-columns: 1fr auto auto auto;
  gap: 12px; align-items: center;
  padding: 6px 8px;
  border-bottom: 1px dotted var(--rule);
  font-family: var(--serif); font-size: var(--fz-sm);
}
.lr__doc[data-state="running"] { background: #fdf6e3; }
.lr__doc[data-state="completed"] { background: #f0f7eb; }
.lr__doc[data-state="failed"] { background: #fdecec; }
.lr__doc-name { color: var(--ink); font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lr__doc-pages { font-family: var(--mono); color: var(--ink-mute); font-size: var(--fz-mono-sm); }
.lr__doc-job {
  font-family: var(--mono); font-size: 11px;
  color: var(--blue);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.05em;
}
.lr__doc-empty {
  padding: 12px; text-align: center;
  color: var(--ink-mute); font-family: var(--serif); font-size: var(--fz-sm);
  background: var(--paper-deep); border: 1px dotted var(--rule);
}

.lr__err {
  padding: 12px 16px; margin-bottom: var(--gap-3);
  background: #fff5f5; border: 1px solid var(--red);
  color: var(--red); font-family: var(--mono); font-size: var(--fz-mono-sm);
}
.lr__note {
  margin-bottom: var(--gap-3); padding: 8px 12px;
  background: var(--paper-deep); border: 1px solid var(--rule);
  font-family: var(--mono); font-size: var(--fz-mono-sm); color: var(--ink-soft);
}

.lr__hits-h {
  margin: 0 0 var(--gap-3);
  font-family: var(--serif); color: var(--blue);
  letter-spacing: 0.18em; font-size: var(--fz-h4);
}
.lr__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--gap-3);
}
.lr__card {
  background: var(--paper); border: 1px solid var(--rule);
  border-top: 3px solid var(--ink-mute);
  display: flex; flex-direction: column;
}
.lr__card[data-type="text_block"] { border-top-color: #a83232; }
.lr__card[data-type="heading"]    { border-top-color: #1a4480; }
.lr__card[data-type="table"]      { border-top-color: #7a3a8a; }
.lr__card[data-type="figure"]     { border-top-color: #b86614; }

.lr__card-h {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--rule);
}
.lr__rank {
  font-family: var(--mono); font-weight: 700;
  font-size: 16px; color: var(--red);
  width: 24px; text-align: center;
}
.lr__score {
  margin-left: auto;
  font-family: var(--mono); font-weight: 600;
  font-size: var(--fz-mono-sm); color: var(--blue);
}

.lr__crop-wrap {
  background: var(--paper-deep);
  padding: 12px;
  display: flex; align-items: center; justify-content: center;
  border-bottom: 1px dotted var(--rule);
  max-height: 180px;
  overflow: hidden;
}
.lr__crop {
  background-repeat: no-repeat;
  background-color: #fff;
  border: 1px solid var(--rule);
  box-shadow: var(--shadow-1);
  max-height: 156px;
}

.lr__card-meta { padding: 8px 12px; display: flex; gap: 16px; flex-wrap: wrap; }
.lr__ml {
  font-family: var(--serif); color: var(--ink-mute);
  letter-spacing: 0.15em; font-size: 10px; margin-right: 6px;
}
.lr__mv { font-family: var(--serif); color: var(--ink); font-weight: 600; font-size: var(--fz-sm); }
.lr__mv--mono { font-family: var(--mono); color: var(--blue); font-variant-numeric: tabular-nums; }

.lr__quote {
  padding: 0 12px 12px;
  font-family: var(--serif); font-size: var(--fz-sm);
  line-height: 1.55; color: var(--ink-soft);
  margin: 0;
}
.lr__quote--soft { color: var(--ink-mute); font-style: italic; }

.lr__hint { padding: var(--gap-4); margin-top: var(--gap-4); }
.lr__hint h4 { margin: 0 0 8px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.lr__hint p { font-family: var(--serif); line-height: 1.8; color: var(--ink-soft); margin: 6px 0; }
.lr__hint-cite {
  font-size: var(--fz-mono-sm); font-family: var(--mono); color: var(--ink-mute);
  border-top: 1px dotted var(--rule); padding-top: 8px; margin-top: 12px;
}
.lr__hint-warn {
  font-size: var(--fz-sm); color: #b86614 !important;
  font-weight: 600;
}
</style>
