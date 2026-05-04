<script setup lang="ts">
import { ref, computed } from 'vue'
import { AppPageHead, AppCard, AppTag } from '../../design/primitives'
import LabQueryBar from '../../components/lab/LabQueryBar.vue'
import ChannelColumn from '../../components/lab/ChannelColumn.vue'
import { labApi, type HybridCompareResponse } from '../../api/client'

const loading = ref(false)
const data = ref<HybridCompareResponse | null>(null)
const doGenerate = ref(false)
const error = ref('')

async function run(payload: { query: string; topK: number; candidates: number }) {
  loading.value = true
  data.value = null
  error.value = ''
  try {
    const resp = await labApi.hybrid(payload.query, {
      topK: payload.topK,
      candidates: payload.candidates,
      doGenerate: doGenerate.value,
    })
    data.value = resp.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}

const bm25Channel = computed(() => data.value?.channels.find(c => c.channel === 'bm25'))
const colpaliChannel = computed(() => data.value?.channels.find(c => c.channel === 'colpali'))
const rrfChannel = computed(() => data.value?.channels.find(c => c.channel === 'rrf'))

function totalTime() {
  if (!data.value) return 0
  return data.value.channels.reduce((s, c) => s + c.timing_ms, 0)
}
</script>

<template>
  <div class="lh">
    <AppPageHead
      chapter="A"
      kicker="LAB · 方法对比"
      title="双通道融合"
      subtitle="BM25 文本通道 与 ColPali 视觉通道并排对比，叠加 Reciprocal Rank Fusion 给出融合排序"
      :meta="[
        { label: '入口', value: '/api/lab/hybrid' },
        { label: '基线', value: 'ColPali (单通道)' },
      ]"
      stamp="双通道&#10;融合"
    />

    <AppCard class="lh__bar">
      <LabQueryBar
        :loading="loading"
        :show-candidates="true"
        placeholder="试一试: '什么是 ColPali 的 late interaction 机制?' / '论文的 Recall@5 是多少?'"
        button-label="对比检索"
        @submit="run"
      />
      <label class="lh__opt">
        <input type="checkbox" v-model="doGenerate" :disabled="loading" />
        融合后调用 LLM 生成答案
      </label>
    </AppCard>

    <div v-if="error" class="lh__err">{{ error }}</div>

    <section v-if="data" class="lh__sum">
      <span class="lh__sum-l">总耗时</span>
      <span class="lh__sum-v">{{ totalTime().toFixed(0) }} ms</span>
      <span class="lh__sum-sep"></span>
      <AppTag variant="paper" size="sm">融合通道: RRF</AppTag>
      <AppTag variant="paper" size="sm">候选/通道: {{ bm25Channel?.results.length ?? 0 }}+{{ colpaliChannel?.results.length ?? 0 }}</AppTag>
    </section>

    <section v-if="data" class="lh__grid">
      <ChannelColumn v-if="bm25Channel"    :channel="bm25Channel"    title="文本通道 BM25"   variant="sparse" />
      <ChannelColumn v-if="colpaliChannel" :channel="colpaliChannel" title="视觉通道 ColPali" variant="dense" />
      <ChannelColumn v-if="rrfChannel"     :channel="rrfChannel"     title="RRF 融合排序"     variant="fused" />
    </section>

    <AppCard v-if="data?.answer" class="lh__ans">
      <div class="lh__ans-head">
        <span class="lh__seal">答</span>
        <h3>融合通道生成答案</h3>
      </div>
      <p class="lh__ans-body">{{ data.answer }}</p>
    </AppCard>

    <AppCard v-if="!data && !loading" class="lh__hint">
      <h4>这一页演示了什么？</h4>
      <p>
        <b>BM25</b> (传统稀疏文本检索) 与 <b>ColPali</b> (视觉多向量稠密检索) 各自的优劣不同:
        BM25 擅长术语精确匹配，ColPali 擅长版面/图表。同一问题并排展示两路结果，
        再通过 <b>Reciprocal Rank Fusion</b> (RRF, k=60) 聚合排名，得到稳定融合结果。
      </p>
      <p class="lh__hint-cite">对应开题报告 §3.1.2 双通道多模态检索 + ViDoRAG §混合检索 (公式 3-7)</p>
    </AppCard>
  </div>
</template>

<style scoped>
.lh { max-width: 1400px; margin: 0 auto; }
.lh__bar { padding: var(--gap-4); display: flex; flex-direction: column; gap: var(--gap-3); }
.lh__opt {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--serif); font-size: var(--fz-sm);
  color: var(--ink-soft);
}
.lh__opt input { accent-color: var(--red); }

.lh__err {
  padding: 12px 16px; margin-top: var(--gap-3);
  background: #fff5f5; border: 1px solid var(--red);
  color: var(--red); font-family: var(--mono); font-size: var(--fz-mono-sm);
}

.lh__sum {
  display: flex; align-items: center; gap: 12px;
  margin: var(--gap-4) 0 var(--gap-3);
  padding: 8px 12px;
  background: var(--paper-deep); border: 1px solid var(--rule);
}
.lh__sum-l {
  font-family: var(--serif); font-size: var(--fz-sm);
  color: var(--ink-mute); letter-spacing: 0.15em;
}
.lh__sum-v {
  font-family: var(--mono); font-weight: 700;
  font-size: 18px; color: var(--blue);
  font-variant-numeric: tabular-nums;
}
.lh__sum-sep { flex: 1; }

.lh__grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: var(--gap-3);
  margin-bottom: var(--gap-4);
}
@media (max-width: 1024px) {
  .lh__grid { grid-template-columns: 1fr; }
}

.lh__ans { padding: var(--gap-4); margin-bottom: var(--gap-5); }
.lh__ans-head {
  display: flex; align-items: center; gap: 10px;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 8px; margin-bottom: 12px;
}
.lh__ans-head h3 {
  margin: 0; font-family: var(--serif); font-weight: 700;
  font-size: var(--fz-h3); color: var(--blue);
  letter-spacing: 0.18em;
}
.lh__seal {
  width: 32px; height: 32px;
  background: var(--red); color: var(--paper);
  display: flex; align-items: center; justify-content: center;
  font-family: var(--serif); font-weight: 900;
}
.lh__ans-body {
  font-family: var(--serif); line-height: 1.85;
  color: var(--ink); white-space: pre-wrap;
}

.lh__hint { padding: var(--gap-4); margin-top: var(--gap-4); }
.lh__hint h4 {
  margin: 0 0 8px; font-family: var(--serif);
  color: var(--blue); letter-spacing: 0.15em;
}
.lh__hint p { font-family: var(--serif); line-height: 1.8; color: var(--ink-soft); margin: 6px 0; }
.lh__hint-cite {
  font-size: var(--fz-mono-sm); font-family: var(--mono);
  color: var(--ink-mute); letter-spacing: 0.05em;
  border-top: 1px dotted var(--rule); padding-top: 8px; margin-top: 12px;
}
</style>
