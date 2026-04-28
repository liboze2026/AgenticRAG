<script setup lang="ts">
interface Metric {
  label: string
  value: string | number
  unit?: string
  trend?: 'up' | 'down' | 'flat'
  hint?: string
}
withDefaults(defineProps<{
  metrics: Metric[]
  cols?: number
}>(), {
  cols: 4,
})
</script>

<template>
  <div class="mg" :style="{ gridTemplateColumns: `repeat(${cols}, 1fr)` }">
    <div v-for="(m, i) in metrics" :key="i" class="mg__cell">
      <div class="mg__label">{{ m.label }}</div>
      <div class="mg__value">
        {{ m.value }}<span v-if="m.unit" class="mg__unit">{{ m.unit }}</span>
      </div>
      <div v-if="m.hint" class="mg__hint">{{ m.hint }}</div>
    </div>
  </div>
</template>

<style scoped>
.mg {
  display: grid;
  gap: 0;
  border: 1px solid var(--ink);
  background: var(--paper);
}
.mg__cell {
  padding: var(--gap-4) var(--gap-5);
  border-right: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  position: relative;
}
.mg__cell:last-child { border-right: none; }
.mg__cell::before {
  content: '';
  position: absolute;
  top: 6px; left: 6px;
  width: 6px; height: 6px;
  background: var(--red);
  opacity: 0.65;
}

.mg__label {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
  margin-bottom: 8px;
  padding-left: 14px;
}
.mg__value {
  font-family: var(--mono);
  font-weight: 700;
  font-size: 32px;
  color: var(--blue);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.mg__unit {
  font-family: var(--serif);
  font-size: var(--fz-sm);
  color: var(--ink-mute);
  margin-left: 6px;
  font-weight: 400;
}
.mg__hint {
  margin-top: 8px;
  font-family: var(--serif);
  font-style: italic;
  font-size: var(--fz-sm);
  color: var(--ink-soft);
}
</style>
