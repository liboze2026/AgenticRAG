<script setup lang="ts">
withDefaults(defineProps<{
  modelValue?: string | number
  placeholder?: string
  disabled?: boolean
  type?: string
  size?: 'sm' | 'md' | 'lg'
  prefix?: string
  suffix?: string
}>(), {
  type: 'text',
  size: 'md',
})
defineEmits<{
  (e: 'update:modelValue', v: string): void
  (e: 'enter'): void
  (e: 'focus'): void
  (e: 'blur'): void
}>()
</script>

<template>
  <label class="inp" :class="[`inp--${size}`, { 'inp--disabled': disabled }]">
    <span v-if="prefix" class="inp__prefix">{{ prefix }}</span>
    <input
      class="inp__el"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      @keyup.enter="$emit('enter')"
      @focus="$emit('focus')"
      @blur="$emit('blur')"
    />
    <span v-if="suffix" class="inp__suffix">{{ suffix }}</span>
  </label>
</template>

<style scoped>
.inp {
  display: inline-flex;
  align-items: center;
  width: 100%;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-bottom: 1.5px solid var(--ink);
  border-radius: 0;
  transition: border-color var(--dur-fast) var(--ease-paper);
  font-family: var(--serif);
}
.inp:hover { border-color: var(--ink-soft); }
.inp:focus-within {
  border-color: var(--blue);
  border-bottom-color: var(--blue);
  border-bottom-width: 2px;
}
.inp--disabled { opacity: .5; pointer-events: none; }

.inp--sm { min-height: 30px; }
.inp--md { min-height: 38px; }
.inp--lg { min-height: 46px; }

.inp__el {
  flex: 1;
  min-width: 0;
  padding: 0 12px;
  border: none;
  outline: none;
  background: transparent;
  color: var(--ink);
  font: inherit;
  font-size: var(--fz-base);
}
.inp--sm .inp__el { font-size: var(--fz-sm); }
.inp--lg .inp__el { font-size: calc(var(--fz-base) + 1px); }

.inp__el::placeholder {
  color: var(--ink-mute);
  font-style: italic;
}

.inp__prefix, .inp__suffix {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
  padding: 0 10px;
  white-space: nowrap;
}
.inp__prefix { border-right: 1px solid var(--rule-fine); }
.inp__suffix { border-left: 1px solid var(--rule-fine); }
</style>
