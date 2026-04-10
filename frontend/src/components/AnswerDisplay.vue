<template>
  <el-card v-if="answer" style="margin-top: 16px">
    <template #header><span>回答</span></template>
    <div style="white-space: pre-wrap">{{ answer }}</div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{ answer: string }>()
</script>
