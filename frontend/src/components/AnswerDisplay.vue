<template>
  <div v-if="answer" class="answer-card">
    <div class="answer-card__header">
      <div class="answer-card__title-row">
        <svg class="answer-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span class="answer-card__title">系统回答</span>
      </div>
      <el-button size="small" text @click="copyAnswer">
        <svg style="width:13px;height:13px;margin-right:4px;vertical-align:middle" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        复制
      </el-button>
    </div>
    <div class="answer-card__body">
      <template v-for="(seg, i) in segments" :key="i">
        <span v-if="seg.type === 'text'" class="answer-card__text">{{ seg.value }}</span>
        <sup v-else class="answer-card__cite" @click="$emit('cite', seg.index - 1)">[{{ seg.index }}]</sup>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'

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
  ElMessage.success('已复制')
}
</script>

<style scoped>
.answer-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: 8px;
  margin: 12px 0;
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}
.answer-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-base);
}
.answer-card__title-row { display: flex; align-items: center; gap: 8px; }
.answer-card__icon { width: 16px; height: 16px; color: var(--accent); }
.answer-card__title { font-size: 13px; font-weight: 700; color: var(--text-primary); }
.answer-card__body {
  padding: 16px 20px;
  white-space: pre-wrap;
  line-height: 1.8;
  font-size: 14px;
  color: var(--text-primary);
}
.answer-card__text { color: inherit; }
.answer-card__cite {
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  margin: 0 1px;
  vertical-align: super;
  font-family: 'Inter', sans-serif;
  transition: color .15s;
}
.answer-card__cite:hover { color: var(--accent-hover); text-decoration: underline; }
</style>
