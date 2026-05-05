<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { sotaApi } from '../../api/sota'

const rows = ref<any[]>([])
const errMsg = ref('')

async function refresh() {
  const r = await sotaApi.leaderboard()
  if (r.ok) rows.value = r.rows
  else errMsg.value = r.message || r.error_kind || ''
}
onMounted(refresh)

const pivoted = computed(() => {
  const out: Record<string, Record<string, Record<string, any>>> = {}
  for (const r of rows.value) {
    out[r.method] ??= {}
    out[r.method][r.subset] ??= {}
    out[r.method][r.subset][r.metric] = r
  }
  return out
})
const subsets = computed(() => {
  const s = new Set<string>()
  for (const r of rows.value) s.add(r.subset)
  return Array.from(s).sort()
})
const methodNames = computed(() => Object.keys(pivoted.value).sort())

function fmt(v: number | undefined) {
  return v == null ? '—' : v.toFixed(3)
}
</script>

<template>
  <div class="page">
    <h1>排行榜</h1>
    <p class="hint">
      每 (方法, 子集, 指标) 取所有历史 run 中最高值。
      标注 best run id 用于复核。
    </p>
    <button class="btn" @click="refresh">刷新</button>
    <div v-if="errMsg" class="err">{{ errMsg }}</div>
    <div v-else-if="rows.length === 0" class="empty">
      还没有 run。先去实验台启动一次。
    </div>
    <table v-else>
      <thead>
        <tr>
          <th rowspan="2">方法</th>
          <th v-for="s in subsets" :key="s" colspan="2">{{ s }}</th>
        </tr>
        <tr>
          <template v-for="s in subsets" :key="s">
            <th>R@1</th><th>R@3</th>
          </template>
        </tr>
      </thead>
      <tbody>
        <tr v-for="m in methodNames" :key="m">
          <td class="method-name">{{ m }}</td>
          <template v-for="s in subsets" :key="s">
            <td>{{ fmt(pivoted[m][s]?.['recall@1']?.value) }}</td>
            <td>{{ fmt(pivoted[m][s]?.['recall@3']?.value) }}</td>
          </template>
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
.empty { color: #888; margin-top: 24px; }
table { width: 100%; border-collapse: collapse; margin-top: 16px;
        border: 1px solid #2a2f36; }
th, td { border-bottom: 1px solid #2a2f36; padding: 6px 10px; text-align: center; }
th { background: #1a1f26; font-size: 12px; }
.method-name { text-align: left; font-weight: 600; }
.err { color: #f87171; }
</style>
