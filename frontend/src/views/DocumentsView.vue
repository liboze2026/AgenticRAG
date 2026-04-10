<template>
  <div>
    <h2>文档管理</h2>
    <DocumentUpload @uploaded="loadDocuments" />
    <el-divider />
    <DocumentList :documents="documents" @delete="handleDelete" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import DocumentUpload from '../components/DocumentUpload.vue'
import DocumentList from '../components/DocumentList.vue'
import { documentsApi, type DocumentInfo } from '../api/client'

const documents = ref<DocumentInfo[]>([])

async function loadDocuments() {
  const resp = await documentsApi.list()
  documents.value = resp.data
}

async function handleDelete(id: string) {
  await documentsApi.delete(id)
  await loadDocuments()
}

onMounted(loadDocuments)
</script>
