<template>
  <el-card>
    <template #header>Pipeline 配置</template>
    <el-form label-width="140px" v-if="available">
      <el-form-item v-for="(options, key) in available" :key="key" :label="key">
        <el-select v-model="selected[key]" :placeholder="'选择 ' + key" clearable>
          <el-option v-for="opt in options" :key="opt" :label="opt" :value="opt" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="switching" @click="handleSwitch">切换 Pipeline</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { experimentsApi } from '../api/client'

const available = ref<Record<string, string[]> | null>(null)
const selected = ref<Record<string, string | null>>({})
const switching = ref(false)

async function loadPipelines() {
  const resp = await experimentsApi.getPipelines()
  available.value = resp.data.available
  if (resp.data.current) {
    const cur = { ...resp.data.current }
    // generator may be {name, options} dict from backend — flatten to string name
    if (cur.generator && typeof cur.generator === 'object') {
      cur.generator = (cur.generator as Record<string, unknown>).name as string
    }
    selected.value = cur
  }
}

async function handleSwitch() {
  switching.value = true
  try { await experimentsApi.switchPipeline(selected.value) }
  finally { switching.value = false }
}

onMounted(loadPipelines)
</script>
