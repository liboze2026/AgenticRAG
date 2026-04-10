<template>
  <el-card v-if="hasData" style="margin-top: 16px">
    <template #header>
      <span>性能指标</span>
    </template>
    <el-tag v-for="(v, k) in timing" :key="k" style="margin-right: 8px; margin-bottom: 4px" type="info">
      {{ k }}: {{ v.toFixed(1) }} ms
    </el-tag>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ timing: Record<string, number> }>()
const hasData = computed(() => Object.keys(props.timing).length > 0)
</script>
