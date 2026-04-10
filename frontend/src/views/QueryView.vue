<template>
  <div>
    <h2>检索问答</h2>
    <QueryInput :loading="loading" @submit="handleQuery" @retrieve="handleRetrieve" />
    <AnswerDisplay :answer="answer" />
    <EvidencePanel :results="results" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import QueryInput from '../components/QueryInput.vue'
import AnswerDisplay from '../components/AnswerDisplay.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import { queryApi, type RetrievalResult } from '../api/client'

const loading = ref(false)
const answer = ref('')
const results = ref<RetrievalResult[]>([])

async function handleQuery(query: string, topK = 5) {
  loading.value = true; answer.value = ''; results.value = []
  try { const resp = await queryApi.query(query, topK); answer.value = resp.data.answer; results.value = resp.data.sources }
  finally { loading.value = false }
}

async function handleRetrieve(query: string, topK = 5) {
  loading.value = true; answer.value = ''; results.value = []
  try { const resp = await queryApi.retrieve(query, topK); results.value = resp.data.results }
  finally { loading.value = false }
}
</script>
