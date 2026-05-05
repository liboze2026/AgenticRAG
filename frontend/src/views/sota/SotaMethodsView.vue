<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { sotaApi } from '../../api/sota'

const methods = ref<any[]>([])
const errMsg = ref('')

async function refresh() {
  const r = await sotaApi.methods()
  if (r.ok) methods.value = r.methods
  else errMsg.value = r.message || r.error_kind || ''
}
onMounted(refresh)
</script>

<template>
  <div class="page">
    <h1>方法库</h1>
    <p class="hint">
      每个方法独立模块。学术诚信约束: 注册器拒绝任何标记 uses_test_labels=True 的方法。
      Phase 0 仅含 3 条基线; Phase 1+ 将持续追加新方法 (ensemble / VLM-rerank / PRF / 等)。
    </p>
    <div v-if="errMsg" class="err">{{ errMsg }}</div>
    <div v-else class="cards">
      <div v-for="m in methods" :key="m.name" class="card">
        <div class="hd">
          <span class="name">{{ m.name }}</span>
          <span class="ver">v{{ m.version }}</span>
        </div>
        <div class="desc">{{ m.description }}</div>
        <div class="needs">依赖: {{ (m.needs || []).join(', ') || '—' }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 24px; }
.hint { color: #888; font-size: 13px; margin-bottom: 16px; max-width: 800px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
         gap: 12px; margin-top: 16px; }
.card { border: 1px solid #2a2f36; border-radius: 8px; padding: 14px;
        background: #1a1f26; }
.hd { display: flex; align-items: baseline; justify-content: space-between; }
.name { font-weight: 600; font-size: 15px; }
.ver { font-size: 11px; color: #888; }
.desc { margin: 8px 0; color: #d4d4d4; font-size: 13px; line-height: 1.5; }
.needs { font-size: 12px; color: #888; }
.err { color: #f87171; }
</style>
