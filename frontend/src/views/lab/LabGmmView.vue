<script setup lang="ts">
import { ref, computed } from 'vue'
import { AppPageHead, AppCard, AppTag } from '../../design/primitives'
import LabQueryBar from '../../components/lab/LabQueryBar.vue'
import ScoreHistogram from '../../components/lab/ScoreHistogram.vue'
import { labApi, type GmmResponse, type RetrievalResult } from '../../api/client'

const loading = ref(false)
const data = ref<GmmResponse | null>(null)
const error = ref('')

async function run(payload: { query: string; topK: number; candidates: number }) {
  loading.value = true
  data.value = null
  error.value = ''
  try {
    const resp = await labApi.gmm(payload.query, payload.topK, payload.candidates)
    data.value = resp.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}

function imgUrl(r: RetrievalResult) {
  return `/api/images/${r.document_id}/page_${r.page_number}.png`
}
function shortId(id: string) {
  return id.length > 16 ? id.slice(0, 8) + '⋯' + id.slice(-3) : id
}
function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.cssText = 'opacity:.3;filter:grayscale(1)'
}
const ratio = computed(() => {
  if (!data.value) return ''
  const fixed = data.value.fixed_top_k
  const dyn = data.value.dynamic_top_k
  if (fixed === dyn) return '与固定 top-k 等价'
  return dyn > fixed ? `比固定 +${dyn - fixed}` : `比固定 ${dyn - fixed}`
})
</script>

<template>
  <div class="lg">
    <AppPageHead
      chapter="C"
      kicker="LAB · 方法对比"
      title="动态深度 (GMM)"
      subtitle="高斯混合模型在候选分数分布上拟合双峰，自动决定 top-k 截断位置，不依赖固定阈值"
      :meta="[
        { label: '入口', value: '/api/lab/gmm' },
        { label: '基线', value: '固定 top-k' },
      ]"
      stamp="动态&#10;深度"
    />

    <AppCard class="lg__bar">
      <LabQueryBar
        :loading="loading"
        :show-candidates="true"
        placeholder="试一试: 同样的问题，看 GMM 怎样自动选取 top-k"
        button-label="拟合·截断"
        @submit="run"
      />
    </AppCard>

    <div v-if="error" class="lg__err">{{ error }}</div>

    <section v-if="data?.note" class="lg__note">{{ data.note }}</section>

    <section v-if="data" class="lg__metrics">
      <div class="lg__met">
        <div class="lg__met-l">固定 top-k (基线)</div>
        <div class="lg__met-v">{{ data.fixed_top_k }}</div>
      </div>
      <div class="lg__met lg__met--accent">
        <div class="lg__met-l">GMM 选取 top-k</div>
        <div class="lg__met-v">{{ data.dynamic_top_k }}</div>
        <div class="lg__met-d">{{ ratio }}</div>
      </div>
      <div class="lg__met">
        <div class="lg__met-l">截断分数</div>
        <div class="lg__met-v">{{ data.cutoff_score.toFixed(3) }}</div>
      </div>
      <div class="lg__met">
        <div class="lg__met-l">候选数</div>
        <div class="lg__met-v">{{ data.histogram.reduce((s, b) => s + b.count, 0) }}</div>
      </div>
    </section>

    <AppCard v-if="data" class="lg__chart">
      <h4 class="lg__chart-h">候选分数分布 + GMM 拟合</h4>
      <ScoreHistogram
        :histogram="data.histogram"
        :components="data.components"
        :cutoff-score="data.cutoff_score"
      />
      <div v-if="data.components.length === 2" class="lg__comp">
        <div class="lg__comp-row">
          <AppTag variant="paper" size="sm">低峰</AppTag>
          μ = {{ data.components[0].mean.toFixed(3) }} ·
          σ² = {{ data.components[0].variance.toFixed(4) }} ·
          权重 = {{ (data.components[0].weight * 100).toFixed(0) }}%
        </div>
        <div class="lg__comp-row">
          <AppTag variant="red" size="sm">高峰</AppTag>
          μ = {{ data.components[1].mean.toFixed(3) }} ·
          σ² = {{ data.components[1].variance.toFixed(4) }} ·
          权重 = {{ (data.components[1].weight * 100).toFixed(0) }}%
        </div>
      </div>
    </AppCard>

    <section v-if="data?.results.length" class="lg__res">
      <h4 class="lg__res-h">GMM 入选结果 ({{ data.results.length }} 页)</h4>
      <ol class="lg__list">
        <li v-for="(r, i) in data.results" :key="i" class="lg__item">
          <span class="lg__rank">{{ i + 1 }}</span>
          <div class="lg__thumb">
            <img :src="imgUrl(r)" loading="lazy" alt="page" @error="onImgError" />
          </div>
          <div class="lg__meta">
            <div><span class="lg__ml">页</span><span class="lg__mv">{{ r.page_number }}</span></div>
            <div><span class="lg__ml">分</span><span class="lg__mv lg__mv--mono">{{ r.score.toFixed(4) }}</span></div>
            <div><span class="lg__ml">文档</span><span class="lg__mv lg__mv--mono">{{ shortId(r.document_id) }}</span></div>
          </div>
        </li>
      </ol>
    </section>

    <AppCard v-if="!data && !loading" class="lg__hint">
      <h4>这一页演示了什么？</h4>
      <p>
        固定 top-k 不管问题难易，永远返回同样多页 — 简单问题取多了引入噪声，难题取少了漏证据。
        <b>GMM 动态深度</b>: 把候选分数视为「相关」+「噪声」两个高斯分布的混合，
        拟合后高斯峰边界即为自然截断位置。问题易 → 高峰窄 → 取少；问题难 → 分布弥散 → 取多。
      </p>
      <p class="lg__hint-cite">对应开题报告 §3.1.3 检索增强机制 (公式 3-8)</p>
    </AppCard>
  </div>
</template>

<style scoped>
.lg { max-width: 1100px; margin: 0 auto; }
.lg__bar { padding: var(--gap-4); }

.lg__err {
  padding: 12px 16px; margin-top: var(--gap-3);
  background: #fff5f5; border: 1px solid var(--red);
  color: var(--red); font-family: var(--mono); font-size: var(--fz-mono-sm);
}
.lg__note {
  margin: var(--gap-3) 0; padding: 8px 12px;
  background: var(--paper-deep); border: 1px solid var(--rule);
  font-family: var(--mono); font-size: var(--fz-mono-sm); color: var(--ink-soft);
}

.lg__metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--gap-3);
  margin: var(--gap-4) 0;
}
.lg__met {
  background: var(--paper); border: 1px solid var(--rule);
  border-top: 3px solid var(--ink-mute);
  padding: 12px 16px;
  display: flex; flex-direction: column; gap: 4px;
}
.lg__met--accent { border-top-color: var(--red); background: var(--paper-deep); }
.lg__met-l {
  font-family: var(--serif); font-size: 11px;
  color: var(--ink-mute); letter-spacing: 0.18em;
}
.lg__met-v {
  font-family: var(--mono); font-weight: 800;
  font-size: 28px; color: var(--blue);
  font-variant-numeric: tabular-nums;
}
.lg__met--accent .lg__met-v { color: var(--red); }
.lg__met-d {
  font-family: var(--mono); font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
}
@media (max-width: 720px) {
  .lg__metrics { grid-template-columns: repeat(2, 1fr); }
}

.lg__chart { padding: var(--gap-4); margin-bottom: var(--gap-4); }
.lg__chart-h {
  margin: 0 0 12px;
  font-family: var(--serif); color: var(--blue);
  letter-spacing: 0.18em; font-size: var(--fz-h4);
}
.lg__comp {
  margin-top: 12px;
  font-family: var(--mono); font-size: var(--fz-mono-sm);
  color: var(--ink-soft);
  display: flex; flex-direction: column; gap: 4px;
}
.lg__comp-row { display: flex; align-items: center; gap: 8px; }

.lg__res-h {
  margin: 0 0 var(--gap-3);
  font-family: var(--serif); color: var(--blue);
  letter-spacing: 0.18em; font-size: var(--fz-h4);
}
.lg__list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: var(--gap-2); }
.lg__item {
  display: grid; grid-template-columns: 32px 90px 1fr;
  gap: 12px; align-items: center;
  padding: 10px 12px;
  background: var(--paper); border: 1px solid var(--rule);
}
.lg__rank {
  font-family: var(--mono); font-weight: 700; font-size: 18px;
  color: var(--red); text-align: center;
}
.lg__thumb {
  height: 60px;
  background: var(--paper-deep); border: 1px solid var(--rule);
  overflow: hidden;
}
.lg__thumb img { width: 100%; height: 100%; object-fit: cover; object-position: top; }
.lg__meta { display: flex; gap: 18px; }
.lg__ml {
  font-family: var(--serif); color: var(--ink-mute);
  letter-spacing: 0.15em; font-size: 10px; margin-right: 6px;
}
.lg__mv { font-family: var(--serif); color: var(--ink); font-weight: 600; }
.lg__mv--mono { font-family: var(--mono); color: var(--blue); font-variant-numeric: tabular-nums; }

.lg__hint { padding: var(--gap-4); margin-top: var(--gap-4); }
.lg__hint h4 { margin: 0 0 8px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.lg__hint p { font-family: var(--serif); line-height: 1.8; color: var(--ink-soft); margin: 6px 0; }
.lg__hint-cite {
  font-size: var(--fz-mono-sm); font-family: var(--mono); color: var(--ink-mute);
  border-top: 1px dotted var(--rule); padding-top: 8px; margin-top: 12px;
}
</style>
