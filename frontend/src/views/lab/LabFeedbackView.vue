<script setup lang="ts">
import { ref } from 'vue'
import { AppPageHead, AppCard, AppButton, AppTag } from '../../design/primitives'
import { labApi, type FeedbackResponse } from '../../api/client'

const query = ref('')
const topK = ref(5)
const candidates = ref(20)
const maxRounds = ref(3)
const doGenerate = ref(true)
const loading = ref(false)
const data = ref<FeedbackResponse | null>(null)
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
    const r = await labApi.feedback(query.value, {
      topK: topK.value, candidates: candidates.value,
      maxRounds: maxRounds.value, doGenerate: doGenerate.value,
    })
    data.value = r.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}

const triggerLabels: Record<string, string> = {
  initial:           '初始检索',
  low_density:       'GMM 低密度 — 邻接扩展',
  missing_caption:   '顶页含图缺图注 — 关键词补检',
  missing_heading:   '候选缺标题元素 — 关键词补检',
  neighbor_expand:   '邻接页扩展',
}
</script>

<template>
  <div class="fb">
    <AppPageHead
      chapter="F"
      kicker="LAB · Phase 7"
      title="反馈式补检索"
      subtitle="GMM 判定证据稳定度 — 不收敛则触发邻接页扩展或类型补检索；多轮轨迹可见"
      :meta="[
        { label: '入口', value: 'POST /api/lab/feedback' },
        { label: '依赖', value: 'sklearn (GMM)，否则单轮退化' },
      ]"
      stamp="LAB&#10;反馈"
    />

    <AppCard class="fb__form">
      <div class="fb__row">
        <input v-model="query" class="fb__inp" type="text" placeholder="例如：图1中的研发投入是多少" @keydown.enter="run" />
        <label class="fb__num"><span>top-k</span><input type="number" v-model.number="topK" min="1" max="20" /></label>
        <label class="fb__num"><span>候选</span><input type="number" v-model.number="candidates" min="4" max="100" /></label>
        <label class="fb__num"><span>轮上限</span><input type="number" v-model.number="maxRounds" min="1" max="6" /></label>
        <label class="fb__chk"><input type="checkbox" v-model="doGenerate" /> 生成答案+VISA</label>
        <AppButton variant="primary" :loading="loading" @click="run">运行</AppButton>
      </div>
      <p v-if="error" class="fb__err">{{ error }}</p>
    </AppCard>

    <AppCard v-if="data" class="fb__sum">
      <div class="fb__meta">
        <AppTag :variant="data.converged ? 'blue' : 'red'" size="sm">{{ data.converged ? '收敛' : '未收敛 (轮上限)' }}</AppTag>
        <span>共 {{ data.rounds.length }} 轮 · 最终 {{ data.final_results.length }} 页</span>
      </div>
      <p v-if="data.note" class="fb__note">{{ data.note }}</p>
    </AppCard>

    <section v-if="data && data.rounds.length" class="fb__rounds">
      <h3>轮次轨迹</h3>
      <ol>
        <li v-for="r in data.rounds" :key="r.round_index" class="fb__round">
          <header>
            <span class="fb__round-no">R{{ r.round_index }}</span>
            <AppTag :variant="r.trigger_reason === 'initial' ? 'blue' : 'red'" size="sm">
              {{ triggerLabels[r.trigger_reason] || r.trigger_reason }}
            </AppTag>
            <span class="fb__round-q">「{{ r.query_used }}」</span>
          </header>
          <div class="fb__round-body">
            <div><span>候选总数</span><strong>{{ r.candidate_count }}</strong></div>
            <div><span>高分候选</span><strong>{{ r.high_score_count }}</strong></div>
            <div><span>本轮新增</span><strong>+{{ r.new_pages_added }}</strong></div>
          </div>
          <p v-if="r.note" class="fb__round-note">{{ r.note }}</p>
        </li>
      </ol>
    </section>

    <AppCard v-if="data && data.final_results.length" class="fb__final">
      <h3>最终候选页 ({{ data.final_results.length }})</h3>
      <ul class="fb__pages">
        <li v-for="(p, i) in data.final_results" :key="`${p.document_id}-${p.page_number}`">
          <AppTag size="sm">[{{ i + 1 }}]</AppTag>
          <span class="fb__doc">{{ p.document_id.slice(0, 8) }}</span>
          <span>页 {{ p.page_number }}</span>
          <span class="fb__score">{{ p.score.toFixed(3) }}</span>
        </li>
      </ul>
    </AppCard>

    <AppCard v-if="data && data.answer" class="fb__answer">
      <h3>答案 (含 [n] 引用)</h3>
      <div class="fb__answer-text">{{ data.answer }}</div>
      <p v-if="data.evidence_regions.length" class="fb__evi">
        VISA 归因：{{ data.evidence_regions.length }} 个 bbox
      </p>
    </AppCard>
  </div>
</template>

<style scoped>
.fb { max-width: 1100px; margin: 0 auto; }

.fb__form { padding: var(--gap-4); margin-bottom: var(--gap-3); }
.fb__row { display: flex; align-items: center; gap: var(--gap-3); flex-wrap: wrap; }
.fb__inp { flex: 1; min-width: 260px; padding: 8px 10px; font-family: var(--serif); border: 1px solid var(--rule); background: var(--paper); }
.fb__inp:focus { outline: 2px solid var(--blue); }
.fb__num, .fb__chk { display: flex; align-items: center; gap: 6px; font-family: var(--serif); font-size: var(--fz-sm); color: var(--ink-soft); }
.fb__num input { width: 60px; padding: 6px 8px; border: 1px solid var(--rule); font-family: var(--mono); }
.fb__err { margin: 8px 0 0; color: var(--red); font-family: var(--mono); font-size: var(--fz-mono-sm); }

.fb__sum { padding: var(--gap-3) var(--gap-4); margin-bottom: var(--gap-3); }
.fb__meta { display: flex; align-items: center; gap: var(--gap-3); }
.fb__meta span { font-family: var(--serif); color: var(--ink-soft); }
.fb__note { margin: 8px 0 0; font-family: var(--serif); color: var(--ink-soft); font-size: var(--fz-sm); }

.fb__rounds { margin-bottom: var(--gap-3); }
.fb__rounds h3 { margin: 0 0 12px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.18em; }
.fb__rounds ol { list-style: none; padding: 0; margin: 0; }
.fb__round {
  background: var(--paper); border: 1px solid var(--rule);
  border-left: 4px solid var(--ink-mute);
  padding: 12px 16px; margin-bottom: 8px;
}
.fb__round:has(.fb__round-no:not(:empty)) { } /* placeholder for SCSS-like */
.fb__round header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.fb__round-no { font-family: var(--mono); font-weight: 800; color: var(--red); width: 28px; }
.fb__round-q { font-family: var(--serif); color: var(--ink-soft); font-style: italic; }
.fb__round-body { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 10px; }
.fb__round-body > div { display: flex; flex-direction: column; gap: 4px; }
.fb__round-body span { font-family: var(--mono); font-size: 10px; color: var(--ink-mute); letter-spacing: 0.15em; }
.fb__round-body strong { font-family: var(--serif); font-weight: 700; color: var(--ink); }
.fb__round-note { margin: 8px 0 0; font-family: var(--serif); color: var(--ink-soft); font-size: var(--fz-sm); }

.fb__final { padding: var(--gap-4); margin-bottom: var(--gap-3); }
.fb__final h3 { margin: 0 0 10px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.fb__pages { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
.fb__pages li { display: flex; align-items: center; gap: 10px; font-family: var(--serif); padding: 6px 0; border-bottom: 1px dotted var(--rule); }
.fb__pages li:last-child { border-bottom: none; }
.fb__doc { font-family: var(--mono); font-size: var(--fz-mono-sm); color: var(--ink-mute); }
.fb__score { margin-left: auto; font-family: var(--mono); color: var(--blue); }

.fb__answer { padding: var(--gap-4); }
.fb__answer h3 { margin: 0 0 10px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.fb__answer-text { font-family: var(--serif); line-height: 1.7; color: var(--ink); white-space: pre-wrap; }
.fb__evi { margin: 10px 0 0; font-family: var(--mono); font-size: var(--fz-mono-sm); color: var(--ink-mute); }
</style>
