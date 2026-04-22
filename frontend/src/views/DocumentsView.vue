<template>
  <div class="documents-view">
    <div class="page-header">
      <h2>文档管理</h2>
      <p>上传 PDF 文档，自动版面分析与多模态向量索引</p>
    </div>
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

<style scoped>
.documents-view { max-width: 1100px; margin: 0 auto; }
.page-header { margin-bottom: 20px; }
.page-header h2 { font-size: 22px; font-weight: 800; color: var(--text-primary); margin: 0 0 4px; }
.page-header p { font-size: 13px; color: var(--text-muted); margin: 0; }
</style>
