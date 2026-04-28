<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { documentsApi, datasetsApi, type DatasetInfo } from '../api/client'
import { AppUpload, AppSelect, msg } from '../design/primitives'

const emit = defineEmits<{ (e: 'uploaded'): void }>()
const uploading = ref(false)
const datasets = ref<DatasetInfo[]>([])
const selectedDataset = ref<number | null>(null)

async function loadDatasets() {
  try {
    const resp = await datasetsApi.list()
    datasets.value = resp.data
  } catch {}
}

async function onSelect(files: File[]) {
  if (uploading.value) return
  uploading.value = true
  try {
    let ok = 0
    for (const file of files) {
      try {
        await documentsApi.upload(file, selectedDataset.value ?? undefined)
        ok++
      } catch {
        msg.error(`${file.name} 上传失败`)
      }
    }
    if (ok) msg.success(`已上传 ${ok} 个文档，开始索引`)
    emit('uploaded')
  } finally {
    uploading.value = false
  }
}

onMounted(loadDatasets)
</script>

<template>
  <div class="du">
    <div class="du__row">
      <label class="du__label">所属数据集</label>
      <div class="du__field">
        <AppSelect
          v-model="selectedDataset"
          :options="datasets.map(d => ({ label: d.name, value: d.id, tag: `${d.document_count}个` }))"
          placeholder="可选，不选择则归入默认"
        />
      </div>
    </div>
    <AppUpload
      accept=".pdf"
      multiple
      :disabled="uploading"
      :hint="uploading ? '上传中⋯' : '点击或拖入 PDF 文档'"
      @select="onSelect"
    />
  </div>
</template>

<style scoped>
.du { display: flex; flex-direction: column; gap: var(--gap-4); }
.du__row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: var(--gap-4);
  align-items: center;
}
.du__label {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--ink);
  letter-spacing: 0.18em;
}
</style>
