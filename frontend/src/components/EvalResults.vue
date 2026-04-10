<template>
  <el-card style="margin-top: 16px" v-if="metrics">
    <template #header>评测结果</template>
    <el-descriptions :column="2" border>
      <el-descriptions-item label="总查询数">{{ metrics.total_queries }}</el-descriptions-item>
      <el-descriptions-item label="MRR">{{ metrics.mrr.toFixed(4) }}</el-descriptions-item>
      <el-descriptions-item v-for="(val, k) in metrics.recall_at_k" :key="k" :label="'Recall@' + k">
        {{ val.toFixed(4) }}
      </el-descriptions-item>
    </el-descriptions>
  </el-card>
</template>

<script setup lang="ts">
import type { EvalMetrics } from '../api/client'
defineProps<{ metrics: EvalMetrics | null }>()
</script>
