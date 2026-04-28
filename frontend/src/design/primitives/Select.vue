<script setup lang="ts">
import { ref, computed } from 'vue'
import Icon from '../Icons.vue'

interface Option { label: string; value: string | number; tag?: string }

const props = withDefaults(defineProps<{
  modelValue?: string | number | null
  options: Option[]
  placeholder?: string
  disabled?: boolean
  size?: 'sm' | 'md' | 'lg'
}>(), {
  placeholder: '请选择',
  size: 'md',
})
const emit = defineEmits<{
  (e: 'update:modelValue', v: string | number | null): void
  (e: 'change', v: string | number | null): void
}>()

const open = ref(false)
const root = ref<HTMLElement | null>(null)

const current = computed(() =>
  props.options.find(o => o.value === props.modelValue) || null
)

function pick(o: Option) {
  emit('update:modelValue', o.value)
  emit('change', o.value)
  open.value = false
}

function onBlur() {
  setTimeout(() => { open.value = false }, 120)
}
</script>

<template>
  <div ref="root" class="sel" :class="[`sel--${size}`, { 'sel--open': open, 'sel--disabled': disabled }]" @blur.capture="onBlur" tabindex="0">
    <button type="button" class="sel__btn" :disabled="disabled" @click="open = !open">
      <span class="sel__val" :class="{ 'sel__val--ph': !current }">
        {{ current ? current.label : placeholder }}
      </span>
      <Icon name="chevron-down" :size="14" class="sel__caret" :class="{ 'sel__caret--up': open }" />
    </button>
    <ul class="sel__menu" v-if="open">
      <li
        v-for="o in options"
        :key="o.value"
        class="sel__opt"
        :class="{ 'sel__opt--active': o.value === modelValue }"
        @mousedown.prevent="pick(o)"
      >
        <span class="sel__opt-label">{{ o.label }}</span>
        <span class="sel__opt-tag" v-if="o.tag">{{ o.tag }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.sel {
  position: relative;
  outline: none;
  width: 100%;
  font-family: var(--serif);
}
.sel--disabled { opacity: .5; pointer-events: none; }

.sel__btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-bottom: 1.5px solid var(--ink);
  color: var(--ink);
  cursor: pointer;
  font-size: var(--fz-base);
  text-align: left;
  transition: border-color var(--dur-fast) var(--ease-paper);
}
.sel--sm .sel__btn { min-height: 30px; font-size: var(--fz-sm); }
.sel--md .sel__btn { min-height: 38px; }
.sel--lg .sel__btn { min-height: 46px; font-size: calc(var(--fz-base) + 1px); }
.sel__btn:hover { border-color: var(--ink-soft); }
.sel--open .sel__btn {
  border-color: var(--blue);
  border-bottom-color: var(--blue);
  border-bottom-width: 2px;
}

.sel__val { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sel__val--ph { color: var(--ink-mute); font-style: italic; }
.sel__caret { color: var(--ink-mute); transition: transform var(--dur-fast); }
.sel__caret--up { transform: rotate(180deg); color: var(--blue); }

.sel__menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0; right: 0;
  background: var(--paper);
  border: 1px solid var(--ink);
  box-shadow: var(--shadow-3);
  z-index: 50;
  list-style: none;
  margin: 0; padding: 4px;
  max-height: 280px;
  overflow-y: auto;
  animation: drop var(--dur-fast) var(--ease-paper);
}
@keyframes drop {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
.sel__opt {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  cursor: pointer;
  border-bottom: 1px dotted var(--rule-fine);
  font-size: var(--fz-base);
  transition: background var(--dur-fast);
}
.sel__opt:last-child { border-bottom: none; }
.sel__opt:hover { background: var(--blue-tint); }
.sel__opt--active { background: var(--paper-deep); color: var(--blue); font-weight: 600; }
.sel__opt--active::before {
  content: '〉';
  color: var(--red);
  margin-right: 4px;
  font-weight: 700;
}
.sel__opt-label { flex: 1; }
.sel__opt-tag {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  text-transform: uppercase;
  letter-spacing: var(--ls-medium);
}
</style>
