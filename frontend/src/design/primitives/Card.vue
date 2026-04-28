<script setup lang="ts">
defineProps<{
  title?: string
  subtitle?: string
  num?: string | number
  flat?: boolean
}>()
</script>

<template>
  <article class="card" :class="{ 'card--flat': flat }">
    <header class="card__head" v-if="title || $slots.head">
      <slot name="head">
        <span class="card__num" v-if="num !== undefined">{{ num }}</span>
        <div class="card__title-block">
          <h3 class="card__title">{{ title }}</h3>
          <p class="card__subtitle" v-if="subtitle">{{ subtitle }}</p>
        </div>
        <span class="card__extra"><slot name="extra" /></span>
      </slot>
    </header>
    <div class="card__body">
      <slot />
    </div>
    <footer class="card__foot" v-if="$slots.foot">
      <slot name="foot" />
    </footer>
  </article>
</template>

<style scoped>
.card {
  position: relative;
  background: var(--paper);
  border: 1px solid var(--rule);
  box-shadow: var(--shadow-2);
}
.card--flat { box-shadow: none; }

.card__head {
  display: flex;
  align-items: baseline;
  gap: var(--gap-4);
  padding: var(--gap-4) var(--gap-5);
  border-bottom: 1px solid var(--rule);
  background: var(--paper-deep);
}
.card__num {
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono);
  color: var(--red);
  background: var(--paper);
  border: 1px solid var(--rule);
  padding: 1px 8px;
  letter-spacing: 0.08em;
  flex-shrink: 0;
  align-self: center;
}
.card__title-block { flex: 1; min-width: 0; }
.card__title {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--ink);
  margin: 0;
  line-height: 1.3;
}
.card__subtitle {
  font-family: var(--serif);
  font-style: italic;
  font-size: var(--fz-sm);
  color: var(--ink-mute);
  margin: 2px 0 0;
}
.card__extra {
  flex-shrink: 0;
  margin-left: auto;
}
.card__body { padding: var(--gap-5); }
.card__foot {
  padding: var(--gap-3) var(--gap-5);
  border-top: 1px dashed var(--rule);
  background: var(--paper-deep);
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
}
</style>
