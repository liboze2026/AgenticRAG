<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { sotaApi } from '../../api/sota'

const route = useRoute()
const id = route.params.id as string
const run = ref<any>(null)
const errMsg = ref('')
let timer: any = null

async function refresh() {
  const r = await sotaApi.getRun(id)
  if (r.ok) {
    run.value = r.run
    errMsg.value = ''
  } else {
    errMsg.value = r.message || r.error_kind || ''
  }
}

async function doCancel() {
  await sotaApi.cancelRun(id)
  await refresh()
}

onMounted(async () => {
  await refresh()
  timer = setInterval(() => {
    if (run.value && ['running', 'queued'].includes(run.value.status)) {
      refresh()
    }
  }, 2000)
})
onUnmounted(() => clearInterval(timer))

function fmt(v: number | undefined | null) {
  return v == null ? '—' : v.toFixed(3)
}
function fmtCi(low: number | undefined | null, hi: number | undefined | null) {
  if (low == null || hi == null) return '—'
  return `[${low.toFixed(2)}, ${hi.toFixed(2)}]`
}
</script>

<template>
  <div class="page">
    <div v-if="errMsg && !run" class="err">{{ errMsg }}</div>
    <div v-else-if="!run">加载中…</div>
    <div v-else>
      <h1>Run <span class="mono">{{ run.id }}</span></h1>
      <div class="meta">
        <span class="badge" :class="run.status">{{ run.status }}</span>
        <button v-if="['running','queued'].includes(run.status)"
                class="btn" @click="doCancel">取消</button>
      </div>

      <h3>配置</h3>
      <pre>{{ JSON.stringify(run.config, null, 2) }}</pre>

      <h3>方法状态</h3>
      <table>
        <thead>
          <tr><th>方法</th><th>状态</th><th>耗时(ms)</th><th>错误类型</th></tr>
        </thead>
        <tbody>
          <tr v-for="m in run.methods" :key="m.method">
            <td>{{ m.method }}</td>
            <td><span class="status-pill" :class="m.status">{{ m.status }}</span></td>
            <td>{{ m.duration_ms }}</td>
            <td>{{ m.error_kind || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <h3>指标</h3>
      <table>
        <thead>
          <tr><th>方法</th><th>子集</th><th>指标</th><th>值</th><th>95% CI</th><th>n</th></tr>
        </thead>
        <tbody>
          <tr v-for="(c, i) in run.metrics" :key="i">
            <td>{{ c.method }}</td>
            <td>{{ c.subset }}</td>
            <td>{{ c.metric }}</td>
            <td><b>{{ fmt(c.value) }}</b></td>
            <td>{{ fmtCi(c.ci_low, c.ci_high) }}</td>
            <td>{{ c.n_queries }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 24px; }
.mono { font-family: ui-monospace, monospace; }
.meta { display: flex; gap: 12px; align-items: center; margin: 8px 0 24px 0; }
.badge { padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600;
         border: 1px solid #2a2f36; }
.badge.running, .badge.queued { background: #1a3a6a; color: #9bc1ff; }
.badge.completed { background: #163d2c; color: #6dd49a; }
.badge.partial { background: #3d2f0b; color: #fbbf24; }
.badge.failed { background: #3d161a; color: #f87171; }
.badge.cancelled { background: #2a2f36; color: #888; }
.btn { padding: 4px 12px; border-radius: 6px; border: 1px solid #2a2f36;
       background: #1a1f26; color: #eee; cursor: pointer; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; margin-bottom: 24px;
        border: 1px solid #2a2f36; }
th, td { border-bottom: 1px solid #2a2f36; padding: 6px 10px; text-align: left;
         font-size: 13px; }
th { background: #1a1f26; }
pre { background: #0f1217; padding: 12px; border-radius: 6px; font-size: 12px;
      overflow-x: auto; }
h3 { font-size: 13px; margin: 18px 0 6px 0; color: #ccc;
     text-transform: uppercase; letter-spacing: 0.5px; }
.status-pill { padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.status-pill.ok { background: #163d2c; color: #6dd49a; }
.status-pill.partial { background: #3d2f0b; color: #fbbf24; }
.status-pill.failed { background: #3d161a; color: #f87171; }
.status-pill.skipped { background: #2a2f36; color: #888; }
.status-pill.circuit_open { background: #3d161a; color: #f87171; }
.err { color: #f87171; }
</style>
