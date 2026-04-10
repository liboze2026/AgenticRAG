<template>
  <div>
    <h2>实验工作台</h2>
    <PipelineSelector />

    <el-card style="margin-top: 16px">
      <template #header>批量评测</template>
      <div style="margin-bottom: 12px">
        <el-select v-model="datasetId" placeholder="选择数据集 (可选, 用于复现)" clearable style="width: 280px">
          <el-option v-for="d in datasets" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
      </div>
      <el-upload action="" :auto-upload="false" :on-change="handleFileChange" accept=".json">
        <el-button>上传评测数据 (JSON)</el-button>
      </el-upload>
      <div style="margin-top: 8px; font-size: 12px; color: #999">格式: [{"query": "...", "relevant": ["doc_id:page"]}]</div>
      <div style="margin-top: 12px">
        <el-input v-model="note" placeholder="备注（可选，用于区分实验）" style="max-width: 400px; margin-right: 12px" />
        <el-button type="primary" :loading="evaluating" :disabled="!evalData" @click="runEval">运行评测</el-button>
        <el-button :loading="generatingNegs" :disabled="!evalData" @click="generateHardNegs">生成困难负例</el-button>
        <el-button v-if="evalData" @click="downloadEvalData">下载评测数据</el-button>
      </div>
      <div v-if="evalData" style="margin-top: 8px; font-size: 12px; color: #666">
        当前评测数据: {{ evalData.length }} 条 query
        <span v-if="hasHardNegs"> · 已生成困难负例</span>
      </div>
    </el-card>

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
  const a = document.createElement('a')
  a.href = url
  a.download = 'eval_with_hard_negatives.json'
  a.click()
  URL.revokeObjectURL(url)
}

async function loadDatasets() {
  try {
    const resp = await datasetsApi.list()
    datasets.value = resp.data
  } catch {}
}

onMounted(loadDatasets)
</script>
