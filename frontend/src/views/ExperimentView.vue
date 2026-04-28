<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import PipelineSelector from '../components/PipelineSelector.vue'
import EvalResults from '../components/EvalResults.vue'
import ExperimentHistory from '../components/ExperimentHistory.vue'
import { experimentsApi, datasetsApi, type EvalMetrics, type DatasetInfo } from '../api/client'
import {
  AppPageHead, AppCard, AppButton, AppInput, AppSelect, msg,
} from '../design/primitives'
import Icon from '../design/Icons.vue'

type EvalQuery = { query: string; relevant: string[]; hard_negatives?: string[] }

const evalData = ref<EvalQuery[] | null>(null)
const evaluating = ref(false)
const generatingNegs = ref(false)
const metrics = ref<EvalMetrics | null>(null)
const note = ref('')
const datasetId = ref<number | null>(null)
const datasets = ref<DatasetInfo[]>([])
const historyRef = ref<InstanceType<typeof ExperimentHistory> | null>(null)
const hasHardNegs = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

function pickFile() { fileInput.value?.click() }

function onFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = (ev) => {
    try {
      evalData.value = JSON.parse(ev.target?.result as string)
      hasHardNegs.value = evalData.value?.some(q => q.hard_negatives !== undefined) || false
      msg.success(`已加载 ${evalData.value?.length || 0} 条评测查询`)
    } catch {
      msg.error('JSON 格式错误')
    }
  }
  reader.readAsText(f)
  ;(e.target as HTMLInputElement).value = ''
}

async function runEval() {
  if (!evalData.value) return
  evaluating.value = true
  metrics.value = null
  try {
    const resp = await experimentsApi.evaluate(
      evalData.value.map(q => ({ query: q.query, relevant: q.relevant })),
      10, note.value, datasetId.value ?? undefined
    )
    metrics.value = resp.data
    msg.success('评测完成')
    await historyRef.value?.refresh()
  } finally { evaluating.value = false }
}

async function generateHardNegs() {
  if (!evalData.value) return
  generatingNegs.value = true
  try {
    const resp = await experimentsApi.generateHardNegatives(
      evalData.value.map(q => ({ query: q.query, relevant: q.relevant }))
    )
    evalData.value = resp.data.eval_data
    hasHardNegs.value = true
    msg.success('已生成困难负例')
  } finally { generatingNegs.value = false }
}

function downloadEvalData() {
  if (!evalData.value) return
  const blob = new Blob([JSON.stringify(evalData.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'eval_with_hard_negatives.json'
  a.click()
  URL.revokeObjectURL(url)
}

const datasetOptions = computed(() => datasets.value.map(d => ({ label: d.name, value: d.id, tag: `${d.document_count}件` })))

async function loadDatasets() {
  try { const resp = await datasetsApi.list(); datasets.value = resp.data } catch {}
}
onMounted(loadDatasets)
</script>

<template>
  <div class="ev">
    <AppPageHead
      chapter="5"
      kicker="实验评测"
      title="实验评测"
      subtitle="切换检索 / 生成 Pipeline，计算 Recall / MRR，记录实验历史与对比"
      stamp="实验&#10;评测"
    />

    <PipelineSelector />

    <AppCard title="批量评测" subtitle="batch evaluation" :num="'EV'" class="ev__eval">
      <div class="ev__form">
        <div class="ev__row">
          <label class="ev__l">数据集</label>
          <div class="ev__f">
            <AppSelect
              v-model="datasetId"
              :options="datasetOptions"
              placeholder="可选，不选择则使用全部文档"
            />
          </div>
        </div>
        <div class="ev__row">
          <label class="ev__l">实验备注</label>
          <div class="ev__f">
            <AppInput v-model="note" placeholder="可选，简述本次实验" />
          </div>
        </div>

        <div class="ev__data">
          <input
            ref="fileInput"
            type="file"
            accept=".json"
            class="ev__file"
            @change="onFile"
          />
          <AppButton variant="ghost" @click="pickFile">
            <Icon name="upload" :size="13" />
            导入评测 JSON
          </AppButton>
          <AppButton
            variant="primary"
            :loading="evaluating"
            :disabled="!evalData"
            @click="runEval"
          >
            <Icon name="sparkles" :size="13" />
            运行评测
          </AppButton>
          <AppButton
            variant="red"
            :loading="generatingNegs"
            :disabled="!evalData"
            @click="generateHardNegs"
          >
            生成困难负例
          </AppButton>
          <AppButton
            v-if="evalData"
            variant="ghost"
            @click="downloadEvalData"
          >
            <Icon name="doc" :size="13" />
            导出数据
          </AppButton>
        </div>

        <div v-if="evalData" class="ev__hint">
          <span class="ev__hint-l">已加载</span>
          <b>{{ evalData.length }}</b><small> 条</small>
          <span v-if="hasHardNegs" class="ev__hint-neg">· 含困难负例</span>
        </div>
        <div class="ev__fmt">
          <code>格式:</code>
          <span>[{ "query": "...", "relevant": ["doc_id:page"] }, ...]</span>
        </div>
      </div>
    </AppCard>

    <EvalResults :metrics="metrics" />

    <ExperimentHistory ref="historyRef" />
  </div>
</template>

<style scoped>
.ev { max-width: 1280px; margin: 0 auto; }

.ev__eval { margin-top: var(--gap-5); }

.ev__form { display: flex; flex-direction: column; gap: var(--gap-3); }
.ev__row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: var(--gap-4);
  align-items: center;
}
.ev__l {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--ink);
  letter-spacing: 0.18em;
}

.ev__file { position: absolute; opacity: 0; pointer-events: none; width: 0; height: 0; }
.ev__data {
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap-2);
  margin-top: var(--gap-2);
  padding-top: var(--gap-3);
  border-top: 1px dashed var(--rule);
}

.ev__hint {
  display: flex;
  align-items: baseline;
  gap: 4px;
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.1em;
  margin-top: var(--gap-2);
}
.ev__hint-l {
  font-family: var(--serif);
  font-weight: 700;
  color: var(--ink);
  letter-spacing: 0.18em;
  margin-right: 4px;
}
.ev__hint b {
  color: var(--blue);
  font-weight: 700;
  font-size: var(--fz-base);
  font-variant-numeric: tabular-nums;
}
.ev__hint small { color: var(--ink-mute); font-weight: 400; }
.ev__hint-neg { color: var(--red); margin-left: 8px; font-weight: 700; }

.ev__fmt {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink-mute);
  letter-spacing: 0.05em;
  display: flex;
  gap: 6px;
}
.ev__fmt code {
  font-family: var(--serif);
  font-weight: 700;
  color: var(--ink);
  letter-spacing: 0.15em;
}
</style>
