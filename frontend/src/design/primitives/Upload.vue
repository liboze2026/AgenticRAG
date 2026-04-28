<script setup lang="ts">
import { ref } from 'vue'
import Icon from '../Icons.vue'

const props = withDefaults(defineProps<{
  accept?: string
  multiple?: boolean
  disabled?: boolean
  hint?: string
}>(), {
  accept: '.pdf',
  hint: '点击选择 · 或将文件拖入此区',
})
const emit = defineEmits<{
  (e: 'select', files: File[]): void
}>()

const dragOver = ref(false)
const inputEl = ref<HTMLInputElement | null>(null)

function pick() {
  inputEl.value?.click()
}
function onChange(e: Event) {
  const files = Array.from((e.target as HTMLInputElement).files || [])
  if (files.length) emit('select', files)
  ;(e.target as HTMLInputElement).value = ''
}
function onDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  if (props.disabled) return
  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length) emit('select', files)
}
</script>

<template>
  <div
    class="up"
    :class="{ 'up--drag': dragOver, 'up--disabled': disabled }"
    @click="pick"
    @dragover.prevent="dragOver = true"
    @dragleave="dragOver = false"
    @drop="onDrop"
  >
    <input
      ref="inputEl"
      type="file"
      :accept="accept"
      :multiple="multiple"
      :disabled="disabled"
      @change="onChange"
      class="up__input"
    />
    <div class="up__icon"><Icon name="upload" :size="32" /></div>
    <p class="up__hint">{{ hint }}</p>
    <p class="up__sub" v-if="accept">支持格式 · {{ accept }}</p>
  </div>
</template>

<style scoped>
.up {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--gap-7) var(--gap-5);
  border: 1.5px dashed var(--rule);
  background:
    repeating-linear-gradient(45deg,
      var(--paper) 0, var(--paper) 6px,
      var(--paper-deep) 6px, var(--paper-deep) 12px);
  cursor: pointer;
  transition: all var(--dur-base) var(--ease-paper);
  text-align: center;
  color: var(--ink-soft);
}
.up:hover { border-color: var(--blue); color: var(--blue); }
.up--drag {
  border-color: var(--red);
  border-style: solid;
  background: var(--red-tint);
  color: var(--red);
  transform: scale(1.005);
}
.up--disabled { opacity: .5; pointer-events: none; }

.up__input {
  position: absolute;
  width: 0; height: 0;
  opacity: 0;
  pointer-events: none;
}

.up__icon {
  margin-bottom: var(--gap-3);
  color: currentColor;
}
.up__hint {
  font-family: var(--serif);
  font-size: var(--fz-h4);
  font-weight: 600;
  margin: 0 0 6px;
  color: var(--ink);
}
.up--drag .up__hint { color: var(--red); }

.up__sub {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
  margin: 0;
}
</style>
