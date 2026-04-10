<template>
  <div>
    <h2>数据集管理</h2>
    <el-card>
      <template #header>新建数据集</template>
      <el-form :inline="true">
        <el-form-item label="名称">
          <el-input v-model="newName" placeholder="例如: baseline-v1" style="width: 200px" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newDesc" placeholder="可选" style="width: 300px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="create" :loading="creating">创建</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>已有数据集</span>
          <el-button size="small" @click="refresh" :loading="loading">刷新</el-button>
        </div>
      </template>
      <el-table :data="datasets" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" width="200" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="document_count" label="文档数" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="200" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { datasetsApi, type DatasetInfo } from '../api/client'
import { ElMessage, ElMessageBox } from 'element-plus'

const datasets = ref<DatasetInfo[]>([])
const newName = ref('')
const newDesc = ref('')
const loading = ref(false)
const creating = ref(false)

async function refresh() {
  loading.value = true
  try {
    const resp = await datasetsApi.list()
    datasets.value = resp.data
  } finally { loading.value = false }
}

async function create() {
  if (!newName.value.trim()) {
    ElMessage.warning('请输入名称')
    return
  }
  creating.value = true
  try {
    await datasetsApi.create(newName.value.trim(), newDesc.value.trim())
    newName.value = ''
    newDesc.value = ''
    await refresh()
  } finally { creating.value = false }
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该数据集？', '确认', { type: 'warning' })
    await datasetsApi.delete(id)
    await refresh()
  } catch {}
}

onMounted(refresh)
</script>
