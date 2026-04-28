<script setup lang="ts">
import { ref } from 'vue'
import QueryInput from '../components/QueryInput.vue'
import AnswerDisplay from '../components/AnswerDisplay.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import ProvenancePanel from '../components/ProvenancePanel.vue'
import { AppPageHead } from '../design/primitives'
import { queryApi, type RetrievalResult } from '../api/client'

const loading = ref(false)
const answer = ref('')
const results = ref<RetrievalResult[]>([])
const timing = ref<Record<string, number>>({})

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
  const cards = document.querySelectorAll('.ep-card')
  cards[idx]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}
</script>

<template>
  <div class="qv">
    <AppPageHead
      chapter="2"
      kicker="quaerere · 求 索"
      title="检 索 问 答"
      subtitle="单次问询 · 系统呈交检索证据与生成答案 · 完整链路可追溯"
      :meta="[
        { label: '入口', value: '/query' },
        { label: '模式', value: '单 轮' },
      ]"
      stamp="单次&#10;问询"
    />

    <section class="qv__sec">
      <QueryInput :loading="loading" @submit="handleQuery" @retrieve="handleRetrieve" />
    </section>

    <ProvenancePanel v-if="Object.keys(timing).length" :timing="timing" />

    <AnswerDisplay :answer="answer" @cite="scrollToEvidence" />

    <EvidencePanel :results="results" />
  </div>
</template>

<style scoped>
.qv { max-width: 1100px; margin: 0 auto; }
.qv__sec { margin-bottom: var(--gap-5); }
</style>
