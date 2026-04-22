<template>
  <div class="exp-view">
    <div class="exp-view__header">
      <h2 class="exp-view__title">实验评测工作台</h2>
      <p class="exp-view__subtitle">切换检索与生成策略，对比评测指标，记录实验历史</p>
    </div>

    <div class="exp-section-title">Pipeline 配置</div>
    <PipelineSelector />

    <div class="exp-section-title" style="margin-top: 20px">批量评测</div>
    <div class="exp-eval-card">
      <div class="exp-eval-row">
        <el-select v-model="datasetId" placeholder="选择数据集（可选）" clearable style="width: 240px">
          <el-option v-for="d in datasets" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
        <el-input v-model="note" placeholder="实验备注（可选）" style="flex: 1; max-width: 320px" />
      </div>
      <div class="exp-eval-row" style="margin-top: 12px">
        <el-upload action="" :auto-upload="false" :on-change="handleFileChange" accept=".json" style="display:inline-flex">
          <el-button>上传评测数据 (JSON)</el-button>
        </el-upload>
        <el-button type="primary" :loading="evaluating" :disabled="!evalData" @click="runEval">运行评测</el-button>
        <el-button :loading="generatingNegs" :disabled="!evalData" @click="generateHardNegs">生成困难负例</el-button>
        <el-button v-if="evalData" @click="downloadEvalData">下载评测数据</el-button>
      </div>
      <div v-if="evalData" class="exp-data-hint">
        当前评测数据：{{ evalData.length }} 条 query
        <span v-if="hasHardNegs" class="exp-data-hint--negs">· 已生成困难负例</span>
      </div>
      <div class="exp-format-hint">格式: [{"query": "...", "relevant": ["doc_id:page"]}]</div>
    </div>

    <EvalResults :metrics="metrics" />
    <ExperimentHistory ref="historyRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import PipelineSelector from '../components/PipelineSelector.vue'
import EvalResults from '../components/EvalResults.vue'
import ExperimentHistory from '../components/ExperimentHistory.vue'
import { experimentsApi, datasetsApi, type EvalMetrics, type DatasetInfo } from '../api/client'
import { ElMessage } from 'element-plus'

type EvalQuery = { query: string; relevant: string[]; hard_negatives?: string[] }
const evalData = ref<EvalQuery[] | null>(null)
const evaluating = ref(false)
const generatingNegs = ref(false)
const metrics = ref<EvalMetrics | null>(null)
const note = ref('')
const datasetId = ref<number | undefined>(undefined)
const datasets = ref<DatasetInfo[]>([])
const historyRef = ref<any>(null)
const hasHardNegs = ref(false)

function handleFileChange(uploadFile: any) {
  const reader = new FileReader()
  reader.onload = (e) => {
    evalData.value = JSON.parse(e.target?.result as string)
    hasHardNegs.value = evalData.value?.some(q => q.hard_negatives !== undefined) || false
  }
  reader.readAsText(uploadFile.raw)
}

async function runEval() {
  if (!evalData.value) return
  evaluating.value = true; metrics.value = null
  try {
    const resp = await experimentsApi.evaluate(
      evalData.value.map(q => ({ query: q.query, relevant: q.relevant })),
      10, note.value, datasetId.value
    )
    metrics.value = resp.data
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
    ElMessage.success('已生成困难负例')
  } finally { generatingNegs.value = false }
}

function downloadEvalData() {
  if (!evalData.value) return
  const blob = new Blob([JSON.stringify(evalData.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = 'eval_with_hard_negatives.json'; a.click()
  URL.revokeObjectURL(url)
}

async function loadDatasets() {
  try { const resp = await datasetsApi.list(); datasets.value = resp.data } catch {}
}
onMounted(loadDatasets)
</script>

<style scoped>
.exp-view { max-width: 1000px; margin: 0 auto; }
.exp-view__header { margin-bottom: 20px; }
.exp-view__title { font-size: 22px; font-weight: 800; color: var(--text-primary); margin: 0 0 4px; }
.exp-view__subtitle { font-size: 13px; color: var(--text-muted); margin: 0; }

.exp-section-title {
  font-size: 11px; font-weight: 700; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px;
}

.exp-eval-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 16px;
}
.exp-eval-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.exp-data-hint { margin-top: 10px; font-size: 12px; color: var(--text-muted); }
.exp-data-hint--negs { color: var(--success); margin-left: 4px; font-weight: 600; }
.exp-format-hint { margin-top: 6px; font-size: 11px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace; }
</style>
