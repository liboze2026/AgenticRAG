<template>
  <div v-if="results.length" style="margin-top: 16px">
    <h3>检索证据 (Top-{{ results.length }})</h3>
    <el-row :gutter="12">
      <el-col v-for="(r, i) in results" :key="i" :span="8">
        <el-card shadow="hover" @click="selectedIndex = i">
          <div style="text-align: center">
            <img :src="'/api/images/' + r.document_id + '/page_' + r.page_number + '.png'" style="max-width: 100%; max-height: 200px; object-fit: contain" />
          </div>
          <div style="margin-top: 8px; font-size: 12px; color: #666">
            文档: {{ r.document_id }} | 页: {{ r.page_number }} | 分数: {{ r.score.toFixed(4) }}
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-dialog v-model="showDialog" width="80%">
      <img v-if="selectedResult" :src="'/api/images/' + selectedResult.document_id + '/page_' + selectedResult.page_number + '.png'" style="width: 100%" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { RetrievalResult } from '../api/client'

const props = defineProps<{ results: RetrievalResult[] }>()
const selectedIndex = ref(-1)
const showDialog = computed({
  get: () => selectedIndex.value >= 0,
  set: (v) => { if (!v) selectedIndex.value = -1 },
})
const selectedResult = computed(() => selectedIndex.value >= 0 ? props.results[selectedIndex.value] : null)
</script>
