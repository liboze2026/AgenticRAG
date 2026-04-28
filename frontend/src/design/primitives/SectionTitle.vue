<script setup lang="ts">
defineProps<{
  num?: string | number
  title: string
  subtitle?: string
  level?: 'h1' | 'h2' | 'h3'
}>()
</script>

<template>
  <div class="sec" :class="[`sec--${level || 'h2'}`]">
    <div class="sec__line">
      <span class="sec__num" v-if="num !== undefined">{{ num }}</span>
      <h2 class="sec__title">{{ title }}</h2>
      <span class="sec__extra"><slot name="extra" /></span>
    </div>
    <p class="sec__sub" v-if="subtitle">{{ subtitle }}</p>
  </div>
</template>

<style scoped>
.sec { margin-bottom: var(--gap-5); }

.sec__line {
  display: flex;
  align-items: baseline;
  gap: var(--gap-4);
  border-bottom: 1px solid var(--rule);
  padding-bottom: 8px;
}

.sec__num {
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono);
  color: var(--red);
  background: var(--paper-deep);
  border: 1px solid var(--rule);
  padding: 2px 10px;
  letter-spacing: var(--ls-medium);
  flex-shrink: 0;
}

.sec__title {
  font-family: var(--serif);
  font-weight: 700;
  color: var(--blue);
  margin: 0;
  letter-spacing: 0.02em;
  flex: 1;
}

.sec--h1 .sec__title { font-size: var(--fz-h1); }
.sec--h2 .sec__title { font-size: var(--fz-h2); }
.sec--h3 .sec__title { font-size: var(--fz-h3); }

.sec__extra { flex-shrink: 0; margin-left: auto; }

.sec__sub {
  font-family: var(--serif);
  font-style: italic;
  font-size: var(--fz-base);
  color: var(--ink-soft);
  margin: 8px 0 0;
  padding-left: calc(var(--gap-4) + 50px);
}
</style>
