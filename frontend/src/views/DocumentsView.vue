<template>
  <div>
    <h2>文档管理</h2>
    <DocumentUpload @uploaded="loadDocuments" />
    <el-divider />
    <div style="margin-bottom: 12px">
      <el-select v-model="filterDataset" placeholder="按数据集筛选" clearable style="width: 250px" @change="loadDocuments">
        <el-option v-for="d in allDatasets" :key="d.id" :label="d.name" :value="d.id" />
      </el-select>
    </div>
    <DocumentList :documents="documents" @delete="handleDelete" @retry="handleRetry" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import DocumentUpload from '../components/DocumentUpload.vue'
import DocumentList from '../components/DocumentList.vue'
import { documentsApi, datasetsApi, type DocumentInfo, type DatasetInfo } from '../api/client'
import { ElMessage } from 'element-plus'

const documents = ref<DocumentInfo[]>([])
const allDatasets = ref<DatasetInfo[]>([])
const filterDataset = ref<number | undefined>(undefined)

async function loadDocuments() {
  const resp = await documentsApi.list(filterDataset.value)
  documents.value = resp.data
}

async function loadDatasets() {
  try {
    const resp = await datasetsApi.list()
    allDatasets.value = resp.data
  } catch {}
}

async function handleDelete(id: string) {
  await documentsApi.delete(id)
  await loadDocuments()
}

async function handleRetry(id: string) {
  await documentsApi.retry(id)
  ElMessage.success('已重新加入索引队列')
  await loadDocuments()
}

onMounted(() => {
  loadDocuments()
  loadDatasets()
})
</script>
