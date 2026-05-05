<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { sotaApi } from '../../api/sota'

const loading = ref(true)
const subsets = ref<Record<string, any>>({})
const errMsg = ref('')

async function refresh() {
  loading.value = true
  errMsg.value = ''
  try {
    const r = await sotaApi.datasets()
    if (r.ok) subsets.value = r.subsets
    else errMsg.value = r.message || r.error_kind || 'unknown error'
  } catch (e: any) {
    errMsg.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}
onMounted(refresh)
</script>

<template>
  <div class="page">
    <h1>VisDoMBench 数据集</h1>
    <p class="hint">
      4 子集本地元数据状态。Phase 0 仅消费已下载到
      <code>data/sota_runs/datasets/</code> 的 queries.jsonl。
      首次使用前需运行 <code>python scripts/pull_visdom_metadata.py</code>
      把元数据从远程服务器拉到本地。
    </p>
    <button class="btn" @click="refresh" :disabled="loading">
      {{ loading ? '加载中…' : '刷新' }}
    </button>
    <div v-if="errMsg" class="err">{{ errMsg }}</div>
    <table v-else>
      <thead>
        <tr><th>子集</th><th>状态</th><th>查询数</th><th>路径</th></tr>
      </thead>
      <tbody>
        <tr v-for="(info, name) in subsets" :key="name as string">
          <td>{{ name }}</td>
          <td :class="info.status">{{ info.status }}</td>
          <td>{{ info.query_count }}</td>
          <td><code>{{ info.path }}</code></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.page { padding: 24px; }
.hint { color: #888; font-size: 13px; margin-bottom: 16px; }
.btn { padding: 6px 14px; border-radius: 6px; border: 1px solid #2a2f36;
       background: #1a1f26; color: #eee; cursor: pointer; }
.btn:disabled { opacity: 0.6; cursor: wait; }
table { width: 100%; border-collapse: collapse; margin-top: 16px; }
th, td { border-bottom: 1px solid #2a2f36; padding: 8px 12px; text-align: left; }
.ok { color: #4ade80; }
.missing { color: #f87171; }
.empty { color: #fbbf24; }
.err { color: #f87171; margin-top: 12px; }
code { background: #0f1217; padding: 2px 6px; border-radius: 4px; font-size: 12px; }
</style>
