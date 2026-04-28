<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'primary' | 'ghost' | 'red' | 'plain' | 'link'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
  block?: boolean
  type?: 'button' | 'submit' | 'reset'
}>(), {
  variant: 'plain',
  size: 'md',
  type: 'button',
})
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    class="btn"
    :class="[`btn--${variant}`, `btn--${size}`, { 'btn--block': block, 'btn--loading': loading }]"
  >
    <span class="btn__spinner" v-if="loading" />
    <slot />
  </button>
</template>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-family: var(--sans);
  font-weight: 500;
  letter-spacing: 0.04em;
  padding: 0 18px;
  border: 1px solid var(--ink);
  border-radius: var(--radius-1);
  background: var(--paper);
  color: var(--ink);
  white-space: nowrap;
  user-select: none;
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-paper),
              color var(--dur-fast) var(--ease-paper),
              border-color var(--dur-fast) var(--ease-paper),
              transform var(--dur-fast) var(--ease-paper);
}
.btn:hover { background: var(--paper-deep); }
.btn:active { transform: translateY(1px); }
.btn:disabled { opacity: .45; cursor: not-allowed; }
.btn:disabled:hover { background: var(--paper); }

.btn--sm { height: 30px; padding: 0 12px; font-size: 13px; }
.btn--md { height: 38px; padding: 0 18px; font-size: 14px; }
.btn--lg { height: 46px; padding: 0 26px; font-size: 16px; font-weight: 700; }

.btn--primary {
  background: var(--blue);
  color: var(--paper);
  border-color: var(--blue);
}
.btn--primary:hover { background: var(--blue-deep); border-color: var(--blue-deep); }

.btn--red {
  background: var(--red);
  color: var(--paper);
  border-color: var(--red);
}
.btn--red:hover { background: var(--red-deep); border-color: var(--red-deep); }

.btn--ghost {
  background: transparent;
  border-color: var(--ink-mute);
  color: var(--ink);
}
.btn--ghost:hover { background: var(--paper-deep); border-color: var(--ink); }

.btn--link {
  border: none;
  padding: 0 4px;
  height: auto;
  background: transparent;
  color: var(--blue);
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-thickness: 1px;
}
.btn--link:hover { background: transparent; color: var(--red); }

.btn--block { width: 100%; }

.btn__spinner {
  width: 12px; height: 12px;
  border: 1.5px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: btnspin .8s linear infinite;
}
@keyframes btnspin { to { transform: rotate(360deg); } }
</style>
