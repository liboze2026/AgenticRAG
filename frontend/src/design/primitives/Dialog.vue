<script setup lang="ts">
import Icon from '../Icons.vue'

withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  width?: string
  closable?: boolean
}>(), {
  width: '520px',
  closable: true,
})
defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()
</script>

<template>
  <Teleport to="body">
    <Transition name="dlg">
      <div v-if="modelValue" class="dlg" @click.self="closable && $emit('update:modelValue', false)">
        <div class="dlg__panel" :style="{ width }">
          <header class="dlg__head">
            <h3 class="dlg__title">{{ title }}</h3>
            <button v-if="closable" class="dlg__x" @click="$emit('update:modelValue', false)" aria-label="关闭">
              <Icon name="close" :size="16" />
            </button>
          </header>
          <div class="dlg__body">
            <slot />
          </div>
          <footer class="dlg__foot" v-if="$slots.foot">
            <slot name="foot" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.dlg {
  position: fixed; inset: 0;
  background: rgba(15, 25, 50, 0.45);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
  padding: 20px;
}
.dlg__panel {
  background: var(--paper);
  border: 1px solid var(--ink);
  box-shadow: var(--shadow-3);
  max-height: 90vh;
  display: flex; flex-direction: column;
  position: relative;
}
.dlg__panel::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 4px;
  background: var(--blue);
  border-bottom: 1px solid var(--ink);
}
.dlg__head {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--rule);
  background: var(--paper-deep);
}
.dlg__title {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--ink);
  margin: 0;
  flex: 1;
}
.dlg__x {
  width: 32px; height: 32px;
  background: transparent;
  border: 1px solid var(--rule);
  color: var(--ink-mute);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all var(--dur-fast);
}
.dlg__x:hover { color: var(--red); border-color: var(--red); }
.dlg__body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
  font-family: var(--serif);
  font-size: var(--fz-base);
  line-height: var(--lh-base);
}
.dlg__foot {
  padding: 12px 20px;
  border-top: 1px solid var(--rule);
  background: var(--paper-deep);
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.dlg-enter-active, .dlg-leave-active { transition: opacity var(--dur-base) var(--ease-paper); }
.dlg-enter-active .dlg__panel, .dlg-leave-active .dlg__panel { transition: transform var(--dur-base) var(--ease-paper); }
.dlg-enter-from, .dlg-leave-to { opacity: 0; }
.dlg-enter-from .dlg__panel, .dlg-leave-to .dlg__panel { transform: scale(0.96) translateY(8px); }
</style>
