<script setup lang="ts">
import Stamp from './Stamp.vue'

defineProps<{
  chapter?: string         // "01" | "壹" | etc.
  kicker?: string          // 上方小字
  title: string
  subtitle?: string
  meta?: { label: string; value: string }[]
  stamp?: string           // 印章文字
  stampVariant?: 'red' | 'blue' | 'ink'
}>()
</script>

<template>
  <header class="ph">
    <div class="ph__top">
      <div class="ph__kicker" v-if="kicker || chapter">
        <span class="ph__chap" v-if="chapter">第 {{ chapter }} 编</span>
        <span class="ph__sep" v-if="chapter && kicker">│</span>
        <span v-if="kicker">{{ kicker }}</span>
      </div>
      <div class="ph__meta" v-if="meta && meta.length">
        <span v-for="(m, i) in meta" :key="i" class="ph__meta-item">
          <span class="ph__meta-l">{{ m.label }}</span>
          <span class="ph__meta-v">{{ m.value }}</span>
        </span>
      </div>
    </div>

    <div class="ph__title-row">
      <h1 class="ph__title">{{ title }}</h1>
      <Stamp v-if="stamp" :text="stamp" :variant="stampVariant || 'red'" :size="86" class="ph__stamp" />
    </div>
    <p class="ph__sub" v-if="subtitle">{{ subtitle }}</p>

    <div class="ph__rule"></div>
  </header>
</template>

<style scoped>
.ph {
  position: relative;
  padding-bottom: var(--gap-5);
  margin-bottom: var(--gap-6);
}

.ph__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--gap-5);
  margin-bottom: var(--gap-3);
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
  color: var(--ink-mute);
}

.ph__kicker {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ph__chap {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--red);
  text-transform: none;
  letter-spacing: 0.04em;
}
.ph__sep { color: var(--rule); }

.ph__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap-5);
}
.ph__meta-item {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}
.ph__meta-l { color: var(--ink-mute); }
.ph__meta-v { color: var(--blue); font-weight: 700; }

.ph__title-row {
  display: flex;
  align-items: flex-start;
  gap: var(--gap-5);
  position: relative;
}
.ph__title {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h1);
  line-height: 1.1;
  color: var(--ink);
  margin: 0;
  letter-spacing: 0.02em;
  flex: 1;
  animation: ink-bleed var(--dur-slow) var(--ease-paper) both;
}
.ph__stamp {
  flex-shrink: 0;
  margin-top: -8px;
  margin-right: 16px;
}

.ph__sub {
  font-family: var(--serif);
  font-style: italic;
  font-size: var(--fz-h4);
  color: var(--ink-soft);
  border-left: 3px solid var(--blue);
  padding-left: 14px;
  margin: var(--gap-3) 0 0;
  max-width: 760px;
}

.ph__rule {
  margin-top: var(--gap-5);
  height: 4px;
  background:
    linear-gradient(to bottom, var(--ink) 0, var(--ink) 1px, transparent 1px, transparent 3px, var(--rule) 3px, var(--rule) 4px);
}
</style>
