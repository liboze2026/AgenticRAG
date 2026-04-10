<template>
  <div>
    <h2>实验工作台</h2>
    <PipelineSelector />
    <el-card style="margin-top: 16px">
      <template #header>批量评测</template>
      <el-upload action="" :auto-upload="false" :on-change="handleFileChange" accept=".json">
        <el-button>上传评测数据 (JSON)</el-button>
      </el-upload>
      <div style="margin-top: 8px; font-size: 12px; color: #999">格式: [{"query": "...", "relevant": ["doc_id:page"]}]</div>
      <el-button type="primary" :loading="evaluating" :disabled="!evalData" @click="runEval" style="margin-top: 12px">运行评测</el-button>
    </el-card>
    <EvalResults :metrics="metrics" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import PipelineSelector from '../components/PipelineSelector.vue'
import EvalResults from '../components/EvalResults.vue'
import { experimentsApi, type EvalMetrics } from '../api/client'

const evalData = ref<Array<{ query: string; relevant: string[] }> | null>(null)
const evaluating = ref(false)
const metrics = ref<EvalMetrics | null>(null)

function handleFileChange(uploadFile: any) {
  const reader = new FileReader()
  reader.onload = (e) => { evalData.value = JSON.parse(e.target?.result as string) }
  reader.readAsText(uploadFile.raw)
}

async function runEval() {
  if (!evalData.value) return
  evaluating.value = true; metrics.value = null
  try { const resp = await experimentsApi.evaluate(evalData.value); metrics.value = resp.data }
  finally { evaluating.value = false }
}
</script>
