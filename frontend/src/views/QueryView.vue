<template>
  <div class="query-view">
    <div class="query-view__header">
      <h2 class="query-view__title">检索问答</h2>
      <p class="query-view__subtitle">输入问题，系统自动检索相关文档并生成答案，展示完整溯源链路</p>
    </div>
    <QueryInput :loading="loading" @submit="handleQuery" @retrieve="handleRetrieve" />
    <ProvenancePanel :timing="timing" />
    <AnswerDisplay :answer="answer" @cite="scrollToEvidence" />
    <EvidencePanel :results="results" ref="evidenceRef" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import QueryInput from '../components/QueryInput.vue'
import AnswerDisplay from '../components/AnswerDisplay.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import ProvenancePanel from '../components/ProvenancePanel.vue'
import { queryApi, type RetrievalResult } from '../api/client'

const loading = ref(false)
const answer = ref('')
const results = ref<RetrievalResult[]>([])
const timing = ref<Record<string, number>>({})
const evidenceRef = ref()

async function handleQuery(query: string, topK = 5) {
  loading.value = true; answer.value = ''; results.value = []; timing.value = {}
  try {
    const resp = await queryApi.query(query, topK)
    answer.value = resp.data.answer
    results.value = resp.data.sources
    timing.value = resp.data.timing || {}
  } finally { loading.value = false }
}

async function handleRetrieve(query: string, topK = 5) {
  loading.value = true; answer.value = ''; results.value = []; timing.value = {}
  try {
    const resp = await queryApi.retrieve(query, topK)
    results.value = resp.data.results
    timing.value = resp.data.timing || {}
  } finally { loading.value = false }
}

function scrollToEvidence(idx: number) {
  if (evidenceRef.value) {
    const cards = document.querySelectorAll('.evidence-card')
    cards[idx]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }
}
</script>

<style scoped>
.query-view { max-width: 1000px; margin: 0 auto; }
.query-view__header { margin-bottom: 16px; }
.query-view__title { font-size: 22px; font-weight: 800; color: var(--text-primary); margin: 0 0 4px; }
.query-view__subtitle { font-size: 13px; color: var(--text-muted); margin: 0; }
</style>
