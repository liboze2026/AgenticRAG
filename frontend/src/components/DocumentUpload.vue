<template>
  <div>
    <el-select v-model="selectedDataset" placeholder="选择数据集 (可选)" clearable style="width: 250px; margin-bottom: 12px">
      <el-option v-for="d in datasets" :key="d.id" :label="d.name" :value="d.id" />
    </el-select>
    <el-upload drag multiple action="" :auto-upload="false" :on-change="handleFileChange" accept=".pdf">
      <el-icon :size="60"><upload-filled /></el-icon>
      <div>拖拽 PDF 文件到此处，或 <em>点击上传</em></div>
    </el-upload>
    <el-button type="primary" :loading="uploading" :disabled="!files.length" @click="uploadAll" style="margin-top: 12px">
      上传 {{ files.length }} 个文件
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { documentsApi, datasetsApi, type DatasetInfo } from '../api/client'

const emit = defineEmits<{ (e: 'uploaded'): void }>()
const files = ref<File[]>([])
const uploading = ref(false)
const datasets = ref<DatasetInfo[]>([])
const selectedDataset = ref<number | undefined>(undefined)

async function loadDatasets() {
  try {
    const resp = await datasetsApi.list()
    datasets.value = resp.data
  } catch {}
}

function handleFileChange(uploadFile: any) {
  if (uploadFile.raw) files.value.push(uploadFile.raw)
}

async function uploadAll() {
  uploading.value = true
  try {
    for (const file of files.value) await documentsApi.upload(file, selectedDataset.value)
    files.value = []
    emit('uploaded')
  } finally { uploading.value = false }
}

onMounted(loadDatasets)
</script>
