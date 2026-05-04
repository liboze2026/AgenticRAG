<script setup lang="ts">
import { ref } from 'vue'
import { AppPageHead, AppCard, AppButton, AppTag } from '../../design/primitives'
import { labApi, type UnifiedResponse } from '../../api/client'

const query = ref('')
const topK = ref(5)
const candidates = ref(20)
const useHybrid = ref(true)
const useGmm = ref(true)
const useFeedback = ref(true)
const useVisa = ref(true)
const useRegion = ref(false)
const useGraph = ref(true)
const doGenerate = ref(true)

const loading = ref(false)
const data = ref<UnifiedResponse | null>(null)
const error = ref('')

async function run() {
  if (!query.value.trim()) {
    error.value = '请先输入问题'
    return
  }
  error.value = ''
  loading.value = true
  data.value = null
  try {
    const r = await labApi.unified(query.value, {
      topK: topK.value, candidates: candidates.value,
      useHybrid: useHybrid.value, useGmm: useGmm.value,
      useFeedback: useFeedback.value, useVisa: useVisa.value,
      useRegion: useRegion.value, useGraph: useGraph.value,
      doGenerate: doGenerate.value,
    })
    data.value = r.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}

const stageLabels: Record<string, string> = {
  hybrid:   '双通道融合',
  retrieve: '主管道检索',
  gmm:      'GMM 动态深度',
  feedback: '反馈补检索',
  region:   '区域级检索',
  graph:    '局部关系图',
  generate: '答案生成',
  visa:     'VISA 归因',
}
</script>

<template>
  <div class="un">
    <AppPageHead
      chapter="G"
      kicker="LAB · Phase 8"
      title="统一编排"
      subtitle="一键串联 hybrid / gmm / feedback / region / graph / visa — 每阶段单独 ok 状态，互不影响"
      :meta="[
        { label: '入口', value: 'POST /api/lab/unified' },
      ]"
      stamp="LAB&#10;统一"
    />

    <AppCard class="un__form">
      <div class="un__row">
        <input v-model="query" class="un__inp" type="text" placeholder="例如：图1反映的研发投入趋势" @keydown.enter="run" />
        <label class="un__num"><span>top-k</span><input type="number" v-model.number="topK" min="1" max="20" /></label>
        <label class="un__num"><span>候选</span><input type="number" v-model.number="candidates" min="4" max="100" /></label>
        <AppButton variant="primary" :loading="loading" @click="run">运行</AppButton>
      </div>
      <div class="un__flags">
        <label class="un__chk"><input type="checkbox" v-model="useHybrid" /> 双通道融合</label>
        <label class="un__chk"><input type="checkbox" v-model="useGmm" /> GMM 动态深度</label>
        <label class="un__chk"><input type="checkbox" v-model="useFeedback" /> 反馈补检索</label>
        <label class="un__chk"><input type="checkbox" v-model="useGraph" /> 局部关系图</label>
        <label class="un__chk"><input type="checkbox" v-model="useRegion" /> 区域级检索</label>
        <label class="un__chk"><input type="checkbox" v-model="doGenerate" /> 生成答案</label>
        <label class="un__chk"><input type="checkbox" v-model="useVisa" :disabled="!doGenerate" /> VISA 归因</label>
      </div>
      <p v-if="error" class="un__err">{{ error }}</p>
    </AppCard>

    <AppCard v-if="data" class="un__sum">
      <div class="un__sum-meta">
        <span>总耗时</span><strong>{{ data.timing_ms.total_ms?.toFixed(0) ?? '–' }} ms</strong>
        <span>最终页</span><strong>{{ data.final_results.length }}</strong>
        <span v-if="data.region_hits.length">区域命中</span><strong v-if="data.region_hits.length">{{ data.region_hits.length }}</strong>
        <span v-if="data.graph_nodes.length">图节点</span><strong v-if="data.graph_nodes.length">{{ data.graph_nodes.length }}</strong>
        <span v-if="data.graph_edges.length">图边</span><strong v-if="data.graph_edges.length">{{ data.graph_edges.length }}</strong>
        <span v-if="data.evidence_regions.length">VISA bbox</span><strong v-if="data.evidence_regions.length">{{ data.evidence_regions.length }}</strong>
      </div>
      <p v-if="data.note" class="un__note">{{ data.note }}</p>
    </AppCard>

    <section v-if="data && data.stages.length" class="un__stages">
      <h3>阶段轨迹</h3>
      <ol>
        <li v-for="(s, i) in data.stages" :key="i" class="un__stage" :class="{ 'un__stage--bad': !s.ok }">
          <header>
            <span class="un__no">{{ i + 1 }}</span>
            <strong>{{ stageLabels[s.name] || s.name }}</strong>
            <AppTag :variant="s.ok ? 'blue' : 'red'" size="sm">{{ s.ok ? 'OK' : 'FAIL' }}</AppTag>
            <span class="un__t">{{ s.timing_ms.toFixed(0) }} ms</span>
          </header>
          <p v-if="s.note">{{ s.note }}</p>
          <details v-if="s.summary && Object.keys(s.summary).length" class="un__det">
            <summary>summary</summary>
            <pre>{{ JSON.stringify(s.summary, null, 2) }}</pre>
          </details>
        </li>
      </ol>
    </section>

    <AppCard v-if="data && data.answer" class="un__answer">
      <h3>答案</h3>
      <div class="un__txt">{{ data.answer }}</div>
    </AppCard>

    <AppCard v-if="data && data.final_results.length" class="un__pages">
      <h3>最终候选页</h3>
      <ul>
        <li v-for="(p, i) in data.final_results" :key="`${p.document_id}-${p.page_number}`">
          <AppTag size="sm">[{{ i + 1 }}]</AppTag>
          <span class="un__doc">{{ p.document_id.slice(0, 8) }}</span>
          <span>页 {{ p.page_number }}</span>
          <span class="un__score">{{ p.score.toFixed(3) }}</span>
        </li>
      </ul>
    </AppCard>
  </div>
</template>

<style scoped>
.un { max-width: 1100px; margin: 0 auto; }

.un__form { padding: var(--gap-4); margin-bottom: var(--gap-3); }
.un__row { display: flex; align-items: center; gap: var(--gap-3); flex-wrap: wrap; }
.un__inp { flex: 1; min-width: 280px; padding: 8px 10px; font-family: var(--serif); border: 1px solid var(--rule); background: var(--paper); }
.un__inp:focus { outline: 2px solid var(--blue); }
.un__num { display: flex; align-items: center; gap: 6px; font-family: var(--serif); font-size: var(--fz-sm); color: var(--ink-soft); }
.un__num input { width: 60px; padding: 6px 8px; border: 1px solid var(--rule); font-family: var(--mono); }

.un__flags { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 12px; padding-top: 12px; border-top: 1px dotted var(--rule); }
.un__chk { display: flex; align-items: center; gap: 6px; font-family: var(--serif); font-size: var(--fz-sm); color: var(--ink-soft); }
.un__err { margin: 8px 0 0; color: var(--red); font-family: var(--mono); font-size: var(--fz-mono-sm); }

.un__sum { padding: var(--gap-3) var(--gap-4); margin-bottom: var(--gap-3); }
.un__sum-meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.un__sum-meta span { font-family: var(--mono); font-size: 10px; color: var(--ink-mute); letter-spacing: 0.15em; }
.un__sum-meta strong { font-family: var(--serif); font-weight: 700; color: var(--ink); margin-right: 12px; }
.un__note { margin: 8px 0 0; font-family: var(--serif); color: var(--ink-soft); font-size: var(--fz-sm); }

.un__stages { margin-bottom: var(--gap-3); }
.un__stages h3 { margin: 0 0 10px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.un__stages ol { list-style: none; padding: 0; margin: 0; }
.un__stage {
  background: var(--paper); border: 1px solid var(--rule);
  border-left: 4px solid var(--blue);
  padding: 10px 14px; margin-bottom: 6px;
}
.un__stage--bad { border-left-color: var(--red); }
.un__stage header { display: flex; align-items: center; gap: 10px; }
.un__no { font-family: var(--mono); font-weight: 700; color: var(--ink-mute); width: 22px; text-align: center; }
.un__stage strong { font-family: var(--serif); color: var(--ink); flex: 1; letter-spacing: 0.1em; }
.un__t { font-family: var(--mono); font-size: var(--fz-mono-sm); color: var(--blue); }
.un__stage p { margin: 6px 0 0 32px; font-family: var(--serif); font-size: var(--fz-sm); color: var(--ink-soft); }
.un__det { margin: 6px 0 0 32px; font-family: var(--mono); font-size: var(--fz-mono-sm); color: var(--ink-soft); }
.un__det summary { cursor: pointer; color: var(--ink-mute); }
.un__det pre { margin: 6px 0 0; padding: 8px; background: var(--paper-deep); border: 1px solid var(--rule); white-space: pre-wrap; }

.un__answer { padding: var(--gap-4); margin-bottom: var(--gap-3); }
.un__answer h3 { margin: 0 0 10px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.un__txt { font-family: var(--serif); line-height: 1.7; color: var(--ink); white-space: pre-wrap; }

.un__pages { padding: var(--gap-4); }
.un__pages h3 { margin: 0 0 10px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.un__pages ul { list-style: none; padding: 0; margin: 0; }
.un__pages li { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px dotted var(--rule); font-family: var(--serif); }
.un__pages li:last-child { border-bottom: none; }
.un__doc { font-family: var(--mono); font-size: var(--fz-mono-sm); color: var(--ink-mute); }
.un__score { margin-left: auto; font-family: var(--mono); color: var(--blue); }
</style>
