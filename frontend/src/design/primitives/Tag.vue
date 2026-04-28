<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'blue' | 'red' | 'ok' | 'warn' | 'mute' | 'paper'
  size?: 'sm' | 'md'
  outline?: boolean
}>(), {
  variant: 'mute',
  size: 'md',
})
</script>

<template>
  <span class="tag" :class="[`tag--${variant}`, `tag--${size}`, { 'tag--outline': outline }]">
    <slot />
  </span>
</template>

<style scoped>
.tag {
  display: inline-flex;
  align-items: center;
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
  padding: 2px 8px;
  border: 1px solid currentColor;
  background: transparent;
  white-space: nowrap;
  font-weight: 500;
}
.tag--sm { font-size: 10px; padding: 1px 6px; }
.tag--md { font-size: 11px; padding: 2px 8px; }

.tag--blue { color: var(--blue); background: var(--blue-tint); border-color: var(--blue-line); }
.tag--red { color: var(--red); background: var(--red-tint); border-color: var(--red); }
.tag--ok { color: var(--ok); background: var(--ok-tint); border-color: var(--ok); }
.tag--warn { color: var(--warn); background: var(--warn-tint); border-color: var(--warn); }
.tag--mute { color: var(--ink-mute); background: var(--paper-deep); border-color: var(--rule); }
.tag--paper { color: var(--ink); background: var(--paper); border-color: var(--ink); }

.tag--outline { background: transparent; }
</style>
