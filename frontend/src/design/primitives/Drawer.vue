<script setup lang="ts">
import Icon from '../Icons.vue'

withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  width?: string
  side?: 'right' | 'left'
}>(), {
  width: '520px',
  side: 'right',
})
defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()
</script>

<template>
  <Teleport to="body">
    <Transition :name="`drw-${side}`">
      <div v-if="modelValue" class="drw" @click.self="$emit('update:modelValue', false)">
        <aside class="drw__panel" :class="`drw__panel--${side}`" :style="{ width }">
          <header class="drw__head">
            <h3 class="drw__title">{{ title }}</h3>
            <button class="drw__x" @click="$emit('update:modelValue', false)" aria-label="关闭">
              <Icon name="close" :size="16" />
            </button>
          </header>
          <div class="drw__body">
            <slot />
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drw {
  position: fixed; inset: 0;
  background: rgba(15, 25, 50, 0.35);
  z-index: 999;
  display: flex;
}
.drw__panel {
  background: var(--paper);
  display: flex; flex-direction: column;
  height: 100%;
  max-width: 100vw;
  position: relative;
  box-shadow: var(--shadow-3);
}
.drw__panel--right {
  margin-left: auto;
  border-left: 1px solid var(--ink);
}
.drw__panel--left {
  border-right: 1px solid var(--ink);
}

.drw__head {
  display: flex; align-items: center;
  padding: 16px 22px;
  border-bottom: 1px solid var(--ink);
  background: var(--blue-deep);
  color: var(--paper);
}
.drw__title {
  flex: 1;
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--paper);
  margin: 0;
  letter-spacing: 0.04em;
}
.drw__x {
  width: 32px; height: 32px;
  background: transparent;
  border: 1px solid rgba(255,255,255,.3);
  color: var(--paper);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all var(--dur-fast);
}
.drw__x:hover { background: var(--red); border-color: var(--red); }

.drw__body {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
  font-family: var(--serif);
}

.drw-right-enter-active, .drw-right-leave-active,
.drw-left-enter-active, .drw-left-leave-active { transition: opacity var(--dur-base) var(--ease-paper); }
.drw-right-enter-active .drw__panel, .drw-right-leave-active .drw__panel,
.drw-left-enter-active .drw__panel, .drw-left-leave-active .drw__panel {
  transition: transform var(--dur-base) var(--ease-paper);
}
.drw-right-enter-from, .drw-right-leave-to { opacity: 0; }
.drw-right-enter-from .drw__panel, .drw-right-leave-to .drw__panel { transform: translateX(100%); }
.drw-left-enter-from, .drw-left-leave-to { opacity: 0; }
.drw-left-enter-from .drw__panel, .drw-left-leave-to .drw__panel { transform: translateX(-100%); }
</style>
