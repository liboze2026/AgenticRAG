<template>
  <el-table :data="documents" stripe style="width: 100%">
    <el-table-column prop="id" label="ID" width="100" />
    <el-table-column prop="filename" label="文件名" />
    <el-table-column prop="dataset_id" label="数据集" width="100">
      <template #default="{ row }">
        <span v-if="row.dataset_id">#{{ row.dataset_id }}</span>
        <span v-else style="color: #999">—</span>
      </template>
    </el-table-column>
    <el-table-column prop="total_pages" label="总页数" width="80" />
    <el-table-column prop="indexed_pages" label="已索引" width="80" />
    <el-table-column label="状态" width="120">
      <template #default="{ row }">
        <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="160">
      <template #default="{ row }">
        <el-button v-if="row.status === 'failed'" type="warning" size="small" @click="$emit('retry', row.id)">重试</el-button>
        <el-button type="danger" size="small" @click="$emit('delete', row.id)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import type { DocumentInfo } from '../api/client'
defineProps<{ documents: DocumentInfo[] }>()
defineEmits<{ (e: 'delete', id: string): void; (e: 'retry', id: string): void }>()

function statusType(status: string) {
  switch (status) {
    case 'completed': return 'success'
    case 'indexing': return 'warning'
    case 'failed': return 'danger'
    default: return 'info'
  }
}
</script>
