<script setup lang="ts">
import { ref } from 'vue'
import { AppInput, AppButton } from '../design/primitives'
import Icon from '../design/Icons.vue'

defineProps<{ loading: boolean }>()
const emit = defineEmits<{
  (e: 'submit', query: string, topK?: number): void
  (e: 'retrieve', query: string, topK?: number): void
}>()

const query = ref('')
const topK = ref(5)

function send() {
  if (!query.value.trim()) return
  emit('submit', query.value.trim(), topK.value)
}
function justRetrieve() {
  if (!query.value.trim()) return
  emit('retrieve', query.value.trim(), topK.value)
}
function bumpK(d: number) {
  const n = Math.max(1, Math.min(20, topK.value + d))
  topK.value = n
}
</script>

<template>
  <div class="qi">
    <div class="qi__main">
      <AppInput
        v-model="query"
        size="lg"
        placeholder="问 · 系统自动检索相关页面与版面元素"
        prefix="问"
        @enter="send"
      />
    </div>
    <div class="qi__topk">
      <button type="button" class="qi__k-btn" @click="bumpK(-1)" aria-label="减少" :disabled="topK <= 1">
        <Icon name="minus" :size="13" />
      </button>
      <span class="qi__k-val">
        <span class="qi__k-l">top-k</span>
        <span class="qi__k-v">{{ topK }}</span>
      </span>
      <button type="button" class="qi__k-btn" @click="bumpK(1)" aria-label="增加" :disabled="topK >= 20">
        <Icon name="plus" :size="13" />
      </button>
    </div>
    <AppButton variant="primary" size="lg" :loading="loading" :disabled="!query.trim()" @click="send">
      检 · 答
    </AppButton>
    <AppButton variant="ghost" size="lg" :loading="loading" :disabled="!query.trim()" @click="justRetrieve">
      仅 检 索
    </AppButton>
  </div>
</template>

<style scoped>
.qi {
  display: flex;
  align-items: stretch;
  gap: 0;
}
.qi__main { flex: 1; min-width: 0; }
.qi__main :deep(.inp) { border-right: none; }

.qi__topk {
  display: flex;
  align-items: center;
  border: 1px solid var(--rule);
  border-bottom: 1.5px solid var(--ink);
  border-left: none;
  background: var(--paper);
  padding: 0 6px;
}
.qi__k-btn {
  background: transparent;
  border: none;
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  color: var(--ink-mute);
  cursor: pointer;
  transition: color var(--dur-fast);
}
.qi__k-btn:hover:not(:disabled) { color: var(--red); }
.qi__k-btn:disabled { opacity: .35; cursor: not-allowed; }

.qi__k-val {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 12px;
  line-height: 1;
}
.qi__k-l {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.2em;
  color: var(--ink-mute);
  text-transform: uppercase;
}
.qi__k-v {
  font-family: var(--mono);
  font-weight: 700;
  font-size: 18px;
  color: var(--blue);
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

.qi :deep(.btn) {
  border-left: none !important;
}
</style>
