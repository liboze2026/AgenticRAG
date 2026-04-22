<template>
  <div v-if="stages.length" class="prov-panel">
    <div class="prov-panel__header">
      <span class="prov-panel__title">Pipeline 执行链路</span>
      <span class="prov-panel__total">总耗时 {{ totalMs.toFixed(0) }} ms</span>
    </div>
    <div class="prov-panel__steps">
      <template v-for="(stage, i) in stages" :key="stage.name">
        <div class="prov-step">
          <div class="prov-step__pill">
            <svg class="prov-step__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" v-html="stageIcon(stage.name)" />
            <span class="prov-step__label">{{ stageLabel(stage.name) }}</span>
          </div>
          <span class="prov-step__badge">{{ stage.ms.toFixed(1) }} ms</span>
        </div>
        <div v-if="i < stages.length - 1" class="prov-connector">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ timing: Record<string, number> }>()

const STAGE_ORDER = ['encode_query_ms', 'retrieve_ms', 'rerank_ms', 'generate_ms']
const STAGE_LABELS: Record<string, string> = {
  encode_query_ms: '查询编码',
  retrieve_ms: '向量检索',
  rerank_ms: '重排序',
  generate_ms: '答案生成',
}
const STAGE_ICONS: Record<string, string> = {
  encode_query_ms: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  retrieve_ms: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
  rerank_ms: '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
  generate_ms: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
}

const stages = computed(() =>
  STAGE_ORDER
    .filter(k => k in props.timing && k !== 'total_ms')
    .map(k => ({ name: k, ms: props.timing[k] }))
)
const totalMs = computed(() => props.timing['total_ms'] ?? stages.value.reduce((s, x) => s + x.ms, 0))
function stageLabel(name: string) { return STAGE_LABELS[name] || name }
function stageIcon(name: string) { return STAGE_ICONS[name] || '<circle cx="12" cy="12" r="10"/>' }
</script>

<style scoped>
.prov-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 20px;
  margin: 12px 0;
  box-shadow: var(--shadow-sm);
}
.prov-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.prov-panel__title {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.prov-panel__total {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
}
.prov-panel__steps {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.prov-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.prov-step__pill {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--accent-light);
  border: 1px solid #bfdbfe;
  border-radius: 20px;
  padding: 5px 12px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
}
.prov-step__icon { width: 13px; height: 13px; flex-shrink: 0; }
.prov-step__badge {
  font-size: 10px;
  font-weight: 700;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  font-family: 'JetBrains Mono', monospace;
}
.prov-connector {
  color: var(--text-muted);
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}
.prov-connector svg { width: 16px; height: 16px; }
</style>
