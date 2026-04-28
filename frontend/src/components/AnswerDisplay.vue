<script setup lang="ts">
import { computed } from 'vue'
import { msg } from '../design/primitives'
import Icon from '../design/Icons.vue'

const props = defineProps<{ answer: string }>()
defineEmits<{ (e: 'cite', index: number): void }>()

type Segment = { type: 'text'; value: string } | { type: 'cite'; index: number }

const segments = computed<Segment[]>(() => {
  const parts: Segment[] = []
  const re = /\[(\d+)\]/g
  let last = 0; let m: RegExpExecArray | null
  while ((m = re.exec(props.answer)) !== null) {
    if (m.index > last) parts.push({ type: 'text', value: props.answer.slice(last, m.index) })
    parts.push({ type: 'cite', index: parseInt(m[1]) })
    last = m.index + m[0].length
  }
  if (last < props.answer.length) parts.push({ type: 'text', value: props.answer.slice(last) })
  return parts
})

function copyAnswer() {
  navigator.clipboard.writeText(props.answer)
  msg.success('已抄录至剪贴板')
}
</script>

<template>
  <div v-if="answer" class="ans">
    <div class="ans__head">
      <span class="ans__seal">答</span>
      <span class="ans__label">系 统 释 答</span>
      <button class="ans__copy" @click="copyAnswer" title="抄录">
        <Icon name="edit" :size="13" />
        <span>抄　录</span>
      </button>
    </div>
    <div class="ans__body">
      <template v-for="(seg, i) in segments" :key="i">
        <span v-if="seg.type === 'text'" class="ans__text">{{ seg.value }}</span>
        <sup v-else class="ans__cite" @click="$emit('cite', seg.index - 1)">[{{ seg.index }}]</sup>
      </template>
    </div>
  </div>
</template>

<style scoped>
.ans {
  position: relative;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-left: 4px solid var(--red);
  margin: var(--gap-4) 0;
  box-shadow: var(--shadow-2);
}

.ans__head {
  display: flex;
  align-items: center;
  gap: var(--gap-3);
  padding: 10px 18px;
  background: var(--paper-deep);
  border-bottom: 1px dashed var(--rule);
}

.ans__seal {
  font-family: var(--serif);
  font-weight: 900;
  font-size: 18px;
  color: var(--red);
  width: 28px;
  height: 28px;
  border: 2px solid var(--red);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ans__label {
  flex: 1;
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--ink);
  letter-spacing: 0.18em;
}

.ans__copy {
  display: flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: 1px solid var(--rule);
  color: var(--ink-mute);
  padding: 4px 10px;
  font-family: var(--sans);
  font-size: 11px;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-paper);
}
.ans__copy:hover {
  color: var(--red);
  border-color: var(--red);
}

.ans__body {
  padding: 18px 22px;
  font-family: var(--serif);
  font-size: var(--fz-base);
  line-height: var(--lh-loose);
  color: var(--ink);
  white-space: pre-wrap;
  text-indent: 2em;
}

.ans__text { color: inherit; }

.ans__cite {
  display: inline-block;
  font-family: var(--mono);
  font-weight: 700;
  font-size: 10px;
  color: var(--red);
  vertical-align: super;
  cursor: pointer;
  padding: 0 2px;
  margin: 0 1px;
  text-decoration: none;
  border-bottom: 1px solid var(--red);
  transition: all var(--dur-fast);
}
.ans__cite:hover {
  background: var(--red);
  color: var(--paper);
}
</style>
