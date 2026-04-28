<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { experimentsApi } from '../api/client'
import { AppCard, AppSelect, AppButton, msg } from '../design/primitives'

const available = ref<Record<string, string[]> | null>(null)
const selected = ref<Record<string, string | null>>({})
const switching = ref(false)

const moduleLabels: Record<string, string> = {
  processor:        '版面处理',
  document_encoder: '文档编码',
  query_encoder:    '查询编码',
  retriever:        '检索器',
  reranker:         '重排器',
  generator:        '生成器',
  embedder:         '嵌入器',
  text_extractor:   '文本抽取',
  cache:            '缓存',
}

function moduleLabel(k: string) { return moduleLabels[k] || k }

async function loadPipelines() {
  try {
    const resp = await experimentsApi.getPipelines()
    available.value = resp.data.available
    if (resp.data.current) {
      const cur = { ...resp.data.current }
      if (cur.generator && typeof cur.generator === 'object') {
        cur.generator = (cur.generator as Record<string, unknown>).name as string
      }
      selected.value = cur
    }
  } catch {}
}

async function handleSwitch() {
  switching.value = true
  try {
    await experimentsApi.switchPipeline(selected.value)
    msg.success('Pipeline 已切换')
  } catch {
    msg.error('切换失败')
  } finally {
    switching.value = false
  }
}

const moduleEntries = computed(() => {
  if (!available.value) return []
  return Object.entries(available.value).map(([k, opts]) => ({
    key: k,
    label: moduleLabel(k),
    options: opts.map(o => ({ label: o, value: o })),
  }))
})

onMounted(loadPipelines)
</script>

<template>
  <AppCard title="Pipeline 配置" subtitle="各模块可独立切换" :num="'PL'">
    <div v-if="moduleEntries.length" class="ps">
      <div v-for="entry in moduleEntries" :key="entry.key" class="ps__row">
        <label class="ps__label">
          <span class="ps__label-zh">{{ entry.label }}</span>
          <span class="ps__label-en">{{ entry.key }}</span>
        </label>
        <div class="ps__field">
          <AppSelect
            v-model="selected[entry.key]"
            :options="entry.options"
            :placeholder="`选择${entry.label}`"
          />
        </div>
      </div>
      <div class="ps__act">
        <AppButton variant="primary" :loading="switching" @click="handleSwitch">
          应用配置
        </AppButton>
      </div>
    </div>
  </AppCard>
</template>

<style scoped>
.ps { display: flex; flex-direction: column; gap: var(--gap-4); }
.ps__row {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: var(--gap-4);
  align-items: center;
  border-bottom: 1px dotted var(--rule);
  padding-bottom: var(--gap-3);
}
.ps__label {
  display: flex;
  flex-direction: column;
  font-family: var(--serif);
  letter-spacing: 0.05em;
}
.ps__label-zh {
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--ink);
}
.ps__label-en {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
  margin-top: 2px;
}
.ps__field {}

.ps__act {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--gap-3);
}
</style>
