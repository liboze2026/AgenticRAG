<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import DocumentUpload from '../components/DocumentUpload.vue'
import DocumentList from '../components/DocumentList.vue'
import { documentsApi, datasetsApi, type DocumentInfo, type DatasetInfo } from '../api/client'
import { AppPageHead, AppCard, AppSelect, AppButton, AppMetricGrid, msg } from '../design/primitives'
import Icon from '../design/Icons.vue'

const documents = ref<DocumentInfo[]>([])
const allDatasets = ref<DatasetInfo[]>([])
const filterDataset = ref<number | null>(null)
const loading = ref(false)

async function loadDocuments() {
  loading.value = true
  try {
    const resp = await documentsApi.list(filterDataset.value ?? undefined)
    documents.value = resp.data
  } catch {}
  loading.value = false
}

async function loadDatasets() {
  try {
    const resp = await datasetsApi.list()
    allDatasets.value = resp.data
  } catch {}
}

async function handleDelete(id: string) {
  if (!confirm('确认删除此文档？')) return
  await documentsApi.delete(id)
  msg.success('已删除')
  await loadDocuments()
}

async function handleRetry(id: string) {
  await documentsApi.retry(id)
  msg.success('已重新加入索引队列')
  await loadDocuments()
}

const stats = computed(() => [
  { label: '文档总数', value: documents.value.length, unit: '个' },
  { label: '页面总数', value: documents.value.reduce((s, d) => s + (d.total_pages || 0), 0), unit: '页' },
  { label: '已索引', value: documents.value.filter(d => d.status === 'completed').length, unit: '个' },
  { label: '索引失败', value: documents.value.filter(d => d.status === 'failed').length, unit: '个' },
])

const datasetOptions = computed(() => allDatasets.value.map(d => ({ label: d.name, value: d.id, tag: `${d.document_count}件` })))

onMounted(() => {
  loadDocuments()
  loadDatasets()
})
</script>

<template>
  <div class="dv">
    <AppPageHead
      chapter="3"
      kicker="文档管理"
      title="文档管理"
      subtitle="上传 PDF 文档，系统自动进行版面分析与多模态向量索引"
      stamp="文档&#10;管理"
    />

    <AppMetricGrid :metrics="stats" :cols="4" />

    <div class="dv__cards">
      <AppCard title="上传文档" subtitle="upload pdf" :num="'A'">
        <DocumentUpload @uploaded="loadDocuments" />
      </AppCard>
    </div>

    <section class="dv__list">
      <div class="dv__list-head">
        <h3 class="dv__list-title">
          <span class="dv__list-num">B</span>
          文档列表
          <span class="dv__list-count">（共 {{ documents.length }} 个）</span>
        </h3>
        <div class="dv__list-tools">
          <div class="dv__filter">
            <AppSelect
              v-model="filterDataset"
              :options="datasetOptions"
              placeholder="按数据集筛选"
              size="sm"
              @change="loadDocuments"
            />
          </div>
          <AppButton variant="ghost" size="sm" :loading="loading" @click="loadDocuments">
            <Icon name="reload" :size="13" />
            刷新
          </AppButton>
        </div>
      </div>
      <DocumentList :documents="documents" @delete="handleDelete" @retry="handleRetry" />
    </section>
  </div>
</template>

<style scoped>
.dv { max-width: 1280px; margin: 0 auto; }

.dv__cards { margin-top: var(--gap-5); }

.dv__list { margin-top: var(--gap-6); }
.dv__list-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 8px;
  margin-bottom: var(--gap-4);
}
.dv__list-title {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h3);
  color: var(--blue);
  margin: 0;
  letter-spacing: 0.05em;
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.dv__list-num {
  font-family: var(--mono);
  font-size: var(--fz-mono);
  color: var(--red);
  background: var(--paper-deep);
  border: 1px solid var(--rule);
  padding: 2px 10px;
}
.dv__list-count {
  font-family: var(--serif);
  font-weight: 400;
  font-size: var(--fz-base);
  color: var(--ink-mute);
  font-style: italic;
}

.dv__list-tools {
  display: flex;
  align-items: center;
  gap: var(--gap-3);
}
.dv__filter { width: 220px; }
</style>
