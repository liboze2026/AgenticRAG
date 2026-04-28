<script setup lang="ts">
withDefaults(defineProps<{
  modelValue?: string
  placeholder?: string
  disabled?: boolean
  rows?: number
  autosize?: boolean
}>(), {
  rows: 4,
})
defineEmits<{
  (e: 'update:modelValue', v: string): void
}>()
</script>

<template>
  <label class="ta" :class="{ 'ta--disabled': disabled }">
    <textarea
      class="ta__el"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :rows="rows"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />
  </label>
</template>

<style scoped>
.ta {
  display: block;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-bottom: 1.5px solid var(--ink);
  transition: border-color var(--dur-fast) var(--ease-paper);
}
.ta:hover { border-color: var(--ink-soft); }
.ta:focus-within {
  border-color: var(--blue);
  border-bottom-color: var(--blue);
  border-bottom-width: 2px;
}
.ta--disabled { opacity: .5; pointer-events: none; }

.ta__el {
  display: block;
  width: 100%;
  padding: 12px 14px;
  border: none;
  outline: none;
  background: transparent;
  color: var(--ink);
  font-family: var(--serif);
  font-size: var(--fz-base);
  line-height: var(--lh-base);
  resize: vertical;
  min-height: 80px;
}
.ta__el::placeholder {
  color: var(--ink-mute);
  font-style: italic;
}
</style>
