<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ timing: Record<string, number> }>()
const labelMap: Record<string, string> = {
  retrieval_ms: '检索',
  rerank_ms:    '重排',
  generation_ms:'生成',
  embedding_ms: '嵌入',
  total_ms:     '合计',
}

const rows = computed(() => {
  return Object.entries(props.timing || {})
    .filter(([k, v]) => typeof v === 'number' && k !== 'total_ms')
    .map(([k, v]) => ({ key: k, label: labelMap[k] || k, ms: v as number }))
})

const total = computed(() => {
  const t = props.timing?.total_ms
  if (typeof t === 'number') return t
  return rows.value.reduce((s, r) => s + r.ms, 0)
})

function pct(ms: number) {
  if (!total.value) return 0
  return Math.min(100, Math.round((ms / total.value) * 100))
}

const hasData = computed(() => Object.keys(props.timing || {}).length > 0)
</script>

<template>
  <div v-if="hasData" class="tp">
    <div class="tp__head">
      <span class="tp__l">耗时分解</span>
      <span class="tp__total">合计 <b>{{ total.toFixed(0) }}</b><small> ms</small></span>
    </div>
    <ul class="tp__list">
      <li v-for="r in rows" :key="r.key" class="tp__row">
        <span class="tp__name">{{ r.label }}</span>
        <span class="tp__bar">
          <span class="tp__fill" :style="{ width: pct(r.ms) + '%' }"></span>
        </span>
        <span class="tp__val">{{ r.ms.toFixed(0) }}<small> ms</small></span>
        <span class="tp__pct">{{ pct(r.ms) }}<small>%</small></span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.tp {
  background: var(--paper);
  border: 1px solid var(--rule);
  padding: 14px 18px;
}
.tp__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px dashed var(--rule);
  padding-bottom: 8px;
  margin-bottom: 10px;
}
.tp__l {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--ink);
  letter-spacing: 0.15em;
}
.tp__total {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.1em;
}
.tp__total b {
  color: var(--blue);
  font-weight: 700;
  font-size: var(--fz-base);
  margin: 0 2px;
  font-variant-numeric: tabular-nums;
}
.tp__total small { color: var(--ink-mute); font-weight: 400; margin-left: 1px; }

.tp__list { list-style: none; margin: 0; padding: 0; }
.tp__row {
  display: grid;
  grid-template-columns: 80px 1fr 80px 60px;
  gap: 10px;
  align-items: center;
  font-size: var(--fz-sm);
  padding: 7px 0;
  border-bottom: 1px dotted var(--rule-fine);
}
.tp__row:last-child { border-bottom: none; }
.tp__name {
  font-family: var(--serif);
  color: var(--ink-soft);
  letter-spacing: 0.15em;
  font-weight: 600;
}
.tp__bar {
  height: 6px;
  background: var(--paper-deep);
  border: 1px solid var(--rule);
  position: relative;
  overflow: hidden;
}
.tp__fill {
  display: block;
  height: 100%;
  background: var(--red);
  transition: width var(--dur-slow) var(--ease-paper);
}
.tp__val {
  font-family: var(--mono);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  text-align: right;
  color: var(--ink);
}
.tp__val small { color: var(--ink-mute); font-weight: 400; }
.tp__pct {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.tp__pct small { font-size: 9px; }
</style>
