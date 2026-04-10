<template>
  <div style="display: flex; gap: 12px">
    <el-input v-model="query" placeholder="输入问题..." @keyup.enter="$emit('submit', query, topK)" size="large" />
    <el-input-number v-model="topK" :min="1" :max="20" size="large" style="width: 120px" />
    <el-button type="primary" size="large" :loading="loading" @click="$emit('submit', query, topK)">检索问答</el-button>
    <el-button size="large" :loading="loading" @click="$emit('retrieve', query, topK)">仅检索</el-button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ loading: boolean }>()
defineEmits<{ (e: 'submit', query: string, topK?: number): void; (e: 'retrieve', query: string, topK?: number): void }>()
const query = ref('')
const topK = ref(5)
</script>
