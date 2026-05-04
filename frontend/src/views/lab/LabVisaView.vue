<script setup lang="ts">
import { ref, computed } from 'vue'
import { AppPageHead, AppCard, AppTag } from '../../design/primitives'
import LabQueryBar from '../../components/lab/LabQueryBar.vue'
import BboxOverlay from '../../components/lab/BboxOverlay.vue'
import { labApi, type VisaResponse, type EvidenceRegion } from '../../api/client'

const loading = ref(false)
const data = ref<VisaResponse | null>(null)
const error = ref('')
const activeCitation = ref<number | undefined>(undefined)

async function run(payload: { query: string; topK: number }) {
  loading.value = true
  data.value = null
  error.value = ''
  activeCitation.value = undefined
  try {
    const resp = await labApi.visa(payload.query, payload.topK)
    data.value = resp.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}

// Group regions by source page
interface GroupedSource {
  index: number
  documentId: string
  pageNumber: number
  imagePath: string
  pageWidth: number
  pageHeight: number
  regions: EvidenceRegion[]
}

const groupedSources = computed<GroupedSource[]>(() => {
  if (!data.value) return []
  return data.value.sources.map((src, idx) => ({
    index: idx,
    documentId: src.document_id,
    pageNumber: src.page_number,
    imagePath: `/api/images/${src.document_id}/page_${src.page_number}.png`,
    pageWidth: src.layout?.page_width ?? 0,
    pageHeight: src.layout?.page_height ?? 0,
    regions: data.value!.evidence_regions.filter(
      r => r.document_id === src.document_id && r.page_number === src.page_number,
    ),
  }))
})

// Render answer text with [n] markers as clickable spans
const answerWithMarkers = computed(() => {
  if (!data.value?.answer) return [] as Array<{ kind: 'text' | 'cite'; value: string; n?: number }>
  const out: Array<{ kind: 'text' | 'cite'; value: string; n?: number }> = []
  const regex = /\[(\d+)\]/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = regex.exec(data.value.answer)) !== null) {
    if (m.index > last) out.push({ kind: 'text', value: data.value.answer.slice(last, m.index) })
    out.push({ kind: 'cite', value: m[0], n: parseInt(m[1], 10) })
    last = m.index + m[0].length
  }
  if (last < data.value.answer.length) out.push({ kind: 'text', value: data.value.answer.slice(last) })
  return out
})

function clickCite(n: number) {
  activeCitation.value = n
  const el = document.querySelector(`[data-cite="${n}"]`)
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
function pickRegion(r: EvidenceRegion) {
  activeCitation.value = r.citation
}
function totalTime() {
  if (!data.value?.timing_ms) return 0
  return Object.values(data.value.timing_ms).reduce((a, b) => a + b, 0)
}
</script>

<template>
  <div class="lv">
    <AppPageHead
      chapter="B"
      kicker="LAB · 方法对比"
      title="证据归因 (VISA)"
      subtitle="答案中的 [n] 引用直接落到具体版面元素 (段落 / 表格 / 图表)，红框高亮可视化证据位置"
      :meta="[
        { label: '入口', value: '/api/lab/visa' },
        { label: '基线', value: '页级源 (单次检索)' },
      ]"
      stamp="证据&#10;归因"
    />

    <AppCard class="lv__bar">
      <LabQueryBar
        :loading="loading"
        placeholder="试一试: '论文使用了什么数据集?' / '表 1 中 ColPali 的 NDCG 是多少?'"
        button-label="检索·归因"
        @submit="run"
      />
    </AppCard>

    <div v-if="error" class="lv__err">{{ error }}</div>

    <section v-if="data?.note" class="lv__note">{{ data.note }}</section>

    <AppCard v-if="data?.answer" class="lv__ans">
      <div class="lv__ans-head">
        <span class="lv__seal">答</span>
        <h3>归因答案</h3>
        <span class="lv__time">{{ totalTime().toFixed(0) }} ms</span>
      </div>
      <p class="lv__ans-body">
        <template v-for="(piece, i) in answerWithMarkers" :key="i">
          <span v-if="piece.kind === 'text'">{{ piece.value }}</span>
          <a v-else
            class="lv__cite"
            :class="{ 'lv__cite--active': activeCitation === piece.n }"
            @click="clickCite(piece.n!)"
          >{{ piece.value }}</a>
        </template>
      </p>
      <div class="lv__legend">
        <AppTag variant="paper" size="sm">{{ data.evidence_regions.length }} 个证据区域</AppTag>
        <AppTag variant="paper" size="sm">{{ data.sources.length }} 页源</AppTag>
        <span class="lv__legend-h">类型:</span>
        <span class="lv__legend-tag" data-l="正文">正文</span>
        <span class="lv__legend-tag" data-l="表格">表格</span>
        <span class="lv__legend-tag" data-l="图表">图表</span>
        <span class="lv__legend-tag" data-l="标题">标题</span>
      </div>
    </AppCard>

    <section v-if="data?.sources.length" class="lv__pages">
      <article
        v-for="(g, i) in groupedSources"
        :key="i"
        class="lv__page"
        :data-cite="g.index + 1"
      >
        <header class="lv__page-h">
          <span class="lv__cite-no" :class="{ 'lv__cite-no--active': activeCitation === g.index + 1 }">[{{ g.index + 1 }}]</span>
          <span class="lv__page-name">第 {{ g.pageNumber }} 页 · {{ g.documentId.slice(0, 8) }}⋯</span>
          <span class="lv__page-cnt">{{ g.regions.length }} 区域</span>
        </header>
        <BboxOverlay
          :image-url="g.imagePath"
          :regions="g.regions"
          :page-width="g.pageWidth"
          :page-height="g.pageHeight"
          :active-citation="activeCitation"
          @pick="pickRegion"
        />
        <details v-if="g.regions.length" class="lv__regions">
          <summary>证据区域明细 ({{ g.regions.length }})</summary>
          <ol>
            <li v-for="(r, ri) in g.regions" :key="ri" class="lv__reg">
              <span class="lv__reg-l" :data-l="r.label">{{ r.label || '区域' }}</span>
              <span class="lv__reg-s">分:{{ r.score.toFixed(3) }}</span>
              <span class="lv__reg-q">{{ r.quote || '（图像证据，无文本）' }}</span>
            </li>
          </ol>
        </details>
      </article>
    </section>

    <AppCard v-if="!data && !loading" class="lv__hint">
      <h4>这一页演示了什么？</h4>
      <p>
        传统 RAG 只把答案对应到「页级」，用户难以验证答案具体出自页面哪里。
        <b>VISA</b> 风格的证据归因把每条 [n] 引用进一步落到 bbox 区域，
        红框直接画在原页缩略图上，并按版面元素类型 (正文/表格/图表/标题) 着色。
      </p>
      <p class="lv__hint-cite">对应开题报告 §3.1.4 检索增强推理 + 文献 [15] VISA</p>
    </AppCard>
  </div>
</template>

<style scoped>
.lv { max-width: 1200px; margin: 0 auto; }
.lv__bar { padding: var(--gap-4); }

.lv__err {
  padding: 12px 16px; margin-top: var(--gap-3);
  background: #fff5f5; border: 1px solid var(--red);
  color: var(--red); font-family: var(--mono); font-size: var(--fz-mono-sm);
}
.lv__note {
  margin: var(--gap-3) 0;
  padding: 8px 12px;
  background: var(--paper-deep); border: 1px solid var(--rule);
  font-family: var(--mono); font-size: var(--fz-mono-sm); color: var(--ink-soft);
}

.lv__ans { padding: var(--gap-4); margin: var(--gap-3) 0 var(--gap-4); }
.lv__ans-head {
  display: flex; align-items: center; gap: 10px;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 8px; margin-bottom: 12px;
}
.lv__ans-head h3 {
  flex: 1; margin: 0;
  font-family: var(--serif); font-weight: 700;
  font-size: var(--fz-h3); color: var(--blue);
  letter-spacing: 0.18em;
}
.lv__seal {
  width: 32px; height: 32px;
  background: var(--red); color: var(--paper);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--serif); font-weight: 900;
}
.lv__time {
  font-family: var(--mono); font-weight: 700;
  font-size: 16px; color: var(--ink-mute);
}
.lv__ans-body { font-family: var(--serif); line-height: 1.85; color: var(--ink); }
.lv__cite {
  background: var(--red); color: var(--paper);
  padding: 1px 6px; margin: 0 2px;
  font-family: var(--mono); font-weight: 700; font-size: 12px;
  cursor: pointer; user-select: none;
  letter-spacing: 0.05em;
}
.lv__cite:hover { background: var(--blue); }
.lv__cite--active {
  outline: 2px solid var(--ink); outline-offset: 1px;
}

.lv__legend {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  margin-top: 12px; padding-top: 10px;
  border-top: 1px dotted var(--rule);
  font-family: var(--mono); font-size: var(--fz-mono-sm);
}
.lv__legend-h {
  font-family: var(--serif); color: var(--ink-mute);
  letter-spacing: 0.15em; font-size: 11px;
}
.lv__legend-tag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px;
  font-family: var(--serif); font-size: var(--fz-sm);
}
.lv__legend-tag::before {
  content: ''; width: 10px; height: 10px;
  display: inline-block;
}
.lv__legend-tag[data-l="正文"]::before { background: #a83232; }
.lv__legend-tag[data-l="标题"]::before { background: #1a4480; }
.lv__legend-tag[data-l="表格"]::before { background: #7a3a8a; }
.lv__legend-tag[data-l="图表"]::before { background: #b86614; }

.lv__pages { display: flex; flex-direction: column; gap: var(--gap-4); margin-bottom: var(--gap-5); }
.lv__page { background: var(--paper); border: 1px solid var(--rule); }
.lv__page-h {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--rule);
  background: var(--paper-deep);
}
.lv__cite-no {
  background: var(--ink); color: var(--paper);
  font-family: var(--mono); font-weight: 700;
  padding: 2px 8px; font-size: var(--fz-mono-sm);
  letter-spacing: 0.05em;
}
.lv__cite-no--active { background: var(--red); }
.lv__page-name { flex: 1; font-family: var(--serif); color: var(--ink); }
.lv__page-cnt { font-family: var(--mono); font-size: var(--fz-mono-sm); color: var(--ink-mute); }

.lv__regions { padding: 8px 12px; background: var(--paper-deep); border-top: 1px dotted var(--rule); }
.lv__regions summary {
  cursor: pointer; font-family: var(--serif);
  letter-spacing: 0.1em; font-size: var(--fz-sm); color: var(--ink-soft);
}
.lv__regions ol { padding-left: 24px; margin: 8px 0 0; }
.lv__reg {
  display: grid; grid-template-columns: 50px 80px 1fr;
  gap: 10px; padding: 4px 0;
  font-size: var(--fz-mono-sm);
  border-bottom: 1px dotted var(--rule);
}
.lv__reg-l {
  font-family: var(--serif); font-weight: 600;
  letter-spacing: 0.1em;
  padding: 2px 6px;
}
.lv__reg-l[data-l="正文"] { background: #fdecec; color: #a83232; }
.lv__reg-l[data-l="标题"] { background: #e8eef9; color: #1a4480; }
.lv__reg-l[data-l="表格"] { background: #f1ebf6; color: #7a3a8a; }
.lv__reg-l[data-l="图表"] { background: #fbf1e2; color: #b86614; }
.lv__reg-s { font-family: var(--mono); color: var(--blue); font-variant-numeric: tabular-nums; }
.lv__reg-q { font-family: var(--serif); color: var(--ink-soft); line-height: 1.5; }

.lv__hint { padding: var(--gap-4); margin-top: var(--gap-4); }
.lv__hint h4 { margin: 0 0 8px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.lv__hint p { font-family: var(--serif); line-height: 1.8; color: var(--ink-soft); margin: 6px 0; }
.lv__hint-cite {
  font-size: var(--fz-mono-sm); font-family: var(--mono); color: var(--ink-mute);
  border-top: 1px dotted var(--rule); padding-top: 8px; margin-top: 12px;
}
</style>
