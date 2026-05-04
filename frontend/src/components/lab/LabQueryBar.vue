<script setup lang="ts">
import { ref } from 'vue'
import { AppInput, AppButton } from '../../design/primitives'
import Icon from '../../design/Icons.vue'

defineProps<{
  loading: boolean
  placeholder?: string
  buttonLabel?: string
  showTopK?: boolean
  initialTopK?: number
  initialCandidates?: number
  showCandidates?: boolean
}>()

const emit = defineEmits<{
  (e: 'submit', payload: { query: string; topK: number; candidates: number }): void
}>()

const query = ref('')
const topK = ref(5)
const candidates = ref(20)

function bump(target: 'k' | 'c', d: number) {
  if (target === 'k') topK.value = Math.max(1, Math.min(20, topK.value + d))
  else candidates.value = Math.max(4, Math.min(100, candidates.value + d))
}

function send() {
  const q = query.value.trim()
  if (!q) return
  emit('submit', { query: q, topK: topK.value, candidates: candidates.value })
}
</script>

<template>
  <div class="lqb">
    <AppInput
      v-model="query"
      size="lg"
      :placeholder="placeholder ?? '输入问题…'"
      prefix="问"
      class="lqb__in"
      @enter="send"
    />
    <div v-if="showTopK !== false" class="lqb__k">
      <button class="lqb__btn" :disabled="topK <= 1" @click="bump('k', -1)"><Icon name="minus" :size="12" /></button>
      <span class="lqb__lbl">top-k</span>
      <span class="lqb__val">{{ topK }}</span>
      <button class="lqb__btn" :disabled="topK >= 20" @click="bump('k', 1)"><Icon name="plus" :size="12" /></button>
    </div>
    <div v-if="showCandidates" class="lqb__k">
      <button class="lqb__btn" :disabled="candidates <= 4" @click="bump('c', -1)"><Icon name="minus" :size="12" /></button>
      <span class="lqb__lbl">候选</span>
      <span class="lqb__val">{{ candidates }}</span>
      <button class="lqb__btn" :disabled="candidates >= 100" @click="bump('c', 1)"><Icon name="plus" :size="12" /></button>
    </div>
    <AppButton variant="primary" size="lg" :loading="loading" :disabled="!query.trim()" @click="send">
      {{ buttonLabel ?? '运行' }}
    </AppButton>
  </div>
</template>

<style scoped>
.lqb { display: flex; gap: 0; align-items: stretch; }
.lqb__in { flex: 1; min-width: 0; }
.lqb__in :deep(.inp) { border-right: none; }

.lqb__k {
  display: flex; align-items: center;
  border: 1px solid var(--rule);
  border-bottom: 1.5px solid var(--ink);
  border-left: none;
  background: var(--paper);
  padding: 0 4px;
  gap: 2px;
}
.lqb__btn {
  width: 26px; height: 28px;
  background: transparent; border: none;
  display: flex; align-items: center; justify-content: center;
  color: var(--ink-mute); cursor: pointer;
}
.lqb__btn:hover:not(:disabled) { color: var(--red); }
.lqb__btn:disabled { opacity: .35; cursor: not-allowed; }
.lqb__lbl {
  font-family: var(--mono); font-size: 9px; letter-spacing: 0.2em;
  color: var(--ink-mute); text-transform: uppercase;
  padding-left: 4px;
}
.lqb__val {
  font-family: var(--mono); font-weight: 700;
  font-size: 16px; color: var(--blue);
  font-variant-numeric: tabular-nums; padding-right: 4px;
}
.lqb :deep(.btn) { border-left: none !important; }
</style>
