<template>
  <el-upload drag multiple action="" :auto-upload="false" :on-change="handleFileChange" accept=".pdf">
    <el-icon :size="60"><upload-filled /></el-icon>
    <div>拖拽 PDF 文件到此处，或 <em>点击上传</em></div>
  </el-upload>
  <el-button type="primary" :loading="uploading" :disabled="!files.length" @click="uploadAll" style="margin-top: 12px">
    上传 {{ files.length }} 个文件
  </el-button>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { documentsApi } from '../api/client'

const emit = defineEmits<{ (e: 'uploaded'): void }>()
const files = ref<File[]>([])
const uploading = ref(false)

function handleFileChange(uploadFile: any) {
  if (uploadFile.raw) files.value.push(uploadFile.raw)
}

async function uploadAll() {
  uploading.value = true
  try {
    for (const file of files.value) await documentsApi.upload(file)
    files.value = []
    emit('uploaded')
  } finally { uploading.value = false }
}
</script>
