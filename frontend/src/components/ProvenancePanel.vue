<script setup lang="ts">
import { computed } from 'vue'
import Icon from '../design/Icons.vue'

const props = defineProps<{ timing: Record<string, number> }>()

const STAGE_ORDER = ['encode_query_ms', 'retrieve_ms', 'rerank_ms', 'generate_ms']
const STAGE_LABELS: Record<string, string> = {
  encode_query_ms: '查询编码',
  retrieve_ms:     '向量检索',
  rerank_ms:       '重排序',
  generate_ms:     '答案生成',
}
const STAGE_ICONS: Record<string, string> = {
  encode_query_ms: 'search',
  retrieve_ms:     'database',
  rerank_ms:       'filter',
  generate_ms:     'chat',
}

const stages = computed(() =>
  STAGE_ORDER
    .filter(k => k in props.timing && k !== 'total_ms')
    .map((k, i) => ({ name: k, ms: props.timing[k], idx: i + 1 }))
)
const totalMs = computed(() => props.timing['total_ms'] ?? stages.value.reduce((s, x) => s + x.ms, 0))
</script>

<template>
  <div v-if="stages.length" class="pp">
    <div class="pp__head">
      <span class="pp__l">Pipeline 流程</span>
      <span class="pp__t">合计 <b>{{ totalMs.toFixed(0) }}</b><small> ms</small></span>
    </div>
    <ol class="pp__chain">
      <template v-for="(s, i) in stages" :key="s.name">
        <li class="pp__step">
          <span class="pp__no">{{ String(s.idx).padStart(2, '0') }}</span>
          <span class="pp__icon"><Icon :name="STAGE_ICONS[s.name]" :size="13" /></span>
          <span class="pp__name">{{ STAGE_LABELS[s.name] || s.name }}</span>
          <span class="pp__ms">{{ s.ms.toFixed(1) }}<small> ms</small></span>
        </li>
        <li v-if="i < stages.length - 1" class="pp__sep" aria-hidden="true">
          <span class="pp__sep-line"></span>
          <Icon name="chevron-right" :size="12" class="pp__sep-arrow" />
          <span class="pp__sep-line"></span>
        </li>
      </template>
    </ol>
  </div>
</template>

<style scoped>
.pp {
  background: var(--paper);
  border: 1px solid var(--rule);
  padding: 14px 18px;
}
.pp__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px dashed var(--rule);
  padding-bottom: 8px;
  margin-bottom: 12px;
}
.pp__l {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--ink);
  letter-spacing: 0.18em;
}
.pp__t {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.1em;
}
.pp__t b {
  color: var(--blue);
  font-weight: 700;
  font-size: var(--fz-base);
  font-variant-numeric: tabular-nums;
}
.pp__t small { color: var(--ink-mute); font-weight: 400; }

.pp__chain {
  list-style: none;
  margin: 0; padding: 0;
  display: flex;
  align-items: stretch;
  flex-wrap: wrap;
  gap: 0;
}

.pp__step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid var(--rule);
  background: var(--paper-deep);
  font-family: var(--serif);
  flex-shrink: 0;
}
.pp__no {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  font-weight: 700;
  color: var(--red);
}
.pp__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px; height: 22px;
  background: var(--blue);
  color: var(--paper);
}
.pp__name {
  font-size: var(--fz-sm);
  font-weight: 600;
  color: var(--ink);
  letter-spacing: 0.1em;
}
.pp__ms {
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono);
  color: var(--ink-soft);
  font-variant-numeric: tabular-nums;
}
.pp__ms small { color: var(--ink-mute); font-weight: 400; font-size: 9px; }

.pp__sep {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 30px;
  padding: 0 4px;
}
.pp__sep-line {
  flex: 1;
  height: 1px;
  background: var(--rule);
}
.pp__sep-arrow {
  color: var(--red);
  margin: 0 4px;
}
</style>
