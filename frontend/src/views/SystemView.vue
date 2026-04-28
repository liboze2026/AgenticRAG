<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { systemApi, cacheApi, type CacheStats } from '../api/client'
import {
  AppPageHead, AppCard, AppButton, AppTag, msg,
} from '../design/primitives'
import Icon from '../design/Icons.vue'

const health = ref<any>(null)
const cacheData = ref<{ query_cache: CacheStats; generation_cache: CacheStats } | null>(null)
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    const resp = await systemApi.health()
    health.value = resp.data
  } catch {}
  try { await loadCacheStats() } catch {}
  loading.value = false
}

async function loadCacheStats() {
  try {
    const resp = await cacheApi.stats()
    cacheData.value = resp.data
  } catch {}
}

async function clearQueryCache() {
  await cacheApi.clearQuery()
  msg.success('查询缓存已清空')
  await loadCacheStats()
}

async function clearGenCache() {
  await cacheApi.clearGeneration()
  msg.success('生成缓存已清空')
  await loadCacheStats()
}

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(2)} MB`
}

const services = computed(() => [
  {
    name: '后端服务',
    en: 'Backend API',
    state: health.value ? 'ok' : 'unknown',
    detail: health.value ? `状态: ${health.value.status || 'ok'}` : '检测中⋯',
  },
  {
    name: 'Worker 节点',
    en: 'Worker · ColPali',
    state: health.value?.worker?.status === 'ok' ? 'ok' : (health.value ? 'error' : 'unknown'),
    detail: health.value?.worker?.model || (health.value?.worker?.status === 'ok' ? '就绪' : (health.value ? '未连接' : '检测中⋯')),
  },
  {
    name: 'Qdrant 向量库',
    en: 'Qdrant',
    state: health.value?.qdrant?.status === 'ok' ? 'ok' : (health.value ? 'error' : 'unknown'),
    detail: health.value?.qdrant?.status === 'ok' ? '就绪' : (health.value ? '未连接' : '检测中⋯'),
  },
])

function stateLabel(s: string) {
  return ({ ok: '正常', error: '异常', unknown: '检测中' } as Record<string,string>)[s] || s
}
function stateVar(s: string): 'ok' | 'red' | 'mute' {
  return ({ ok: 'ok', error: 'red', unknown: 'mute' } as const)[s as 'ok'] || 'mute'
}

onMounted(refresh)
</script>

<template>
  <div class="sv">
    <AppPageHead
      chapter="6"
      kicker="系统状态"
      title="系统状态"
      subtitle="服务健康检查、缓存统计、系统监控"
      stamp="系统&#10;状态"
    />

    <AppCard title="服务健康" subtitle="health snapshot" :num="'A'">
      <template #extra>
        <AppButton variant="ghost" size="sm" :loading="loading" @click="refresh">
          <Icon name="reload" :size="13" />
          刷新
        </AppButton>
      </template>

      <ul class="sv-svc">
        <li v-for="(s, i) in services" :key="i" class="sv-svc__item" :class="`sv-svc__item--${s.state}`">
          <div class="sv-svc__no">{{ String(i + 1).padStart(2, '0') }}</div>
          <div class="sv-svc__main">
            <div class="sv-svc__name">{{ s.name }}</div>
            <div class="sv-svc__en">{{ s.en }}</div>
          </div>
          <div class="sv-svc__detail">{{ s.detail }}</div>
          <AppTag :variant="stateVar(s.state)" size="md">{{ stateLabel(s.state) }}</AppTag>
        </li>
      </ul>
    </AppCard>

    <AppCard
      v-if="cacheData"
      title="缓存统计"
      subtitle="cache stats"
      :num="'B'"
      class="sv-cache"
    >
      <template #extra>
        <AppButton variant="ghost" size="sm" @click="loadCacheStats">
          <Icon name="reload" :size="13" />
          刷新
        </AppButton>
      </template>

      <div class="sv-cache__grid">
        <div class="sv-cache__cell">
          <div class="sv-cache__head">
            <span class="sv-cache__zh">查询缓存</span>
            <AppTag :variant="cacheData.query_cache.enabled ? 'ok' : 'mute'" size="sm">
              {{ cacheData.query_cache.enabled ? '已启用' : '已关闭' }}
            </AppTag>
          </div>
          <dl class="sv-cache__meta">
            <div><dt>条目数</dt><dd>{{ cacheData.query_cache.entries }}<small> 项</small></dd></div>
            <div><dt>占用空间</dt><dd>{{ formatBytes(cacheData.query_cache.size_bytes) }}</dd></div>
          </dl>
          <AppButton variant="red" size="sm" @click="clearQueryCache">
            <Icon name="trash" :size="13" />
            清空查询缓存
          </AppButton>
        </div>

        <div class="sv-cache__cell">
          <div class="sv-cache__head">
            <span class="sv-cache__zh">生成缓存</span>
            <AppTag :variant="cacheData.generation_cache.enabled ? 'ok' : 'mute'" size="sm">
              {{ cacheData.generation_cache.enabled ? '已启用' : '已关闭' }}
            </AppTag>
          </div>
          <dl class="sv-cache__meta">
            <div><dt>条目数</dt><dd>{{ cacheData.generation_cache.entries }}<small> 项</small></dd></div>
            <div><dt>占用空间</dt><dd>{{ formatBytes(cacheData.generation_cache.size_bytes) }}</dd></div>
          </dl>
          <AppButton variant="red" size="sm" @click="clearGenCache">
            <Icon name="trash" :size="13" />
            清空生成缓存
          </AppButton>
        </div>
      </div>
    </AppCard>
  </div>
</template>

<style scoped>
.sv { max-width: 980px; margin: 0 auto; }

.sv-svc {
  list-style: none;
  margin: 0; padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  border-top: 1px solid var(--rule);
}
.sv-svc__item {
  display: grid;
  grid-template-columns: 50px 1fr auto auto;
  gap: var(--gap-4);
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid var(--rule);
  border-left: 3px solid transparent;
  padding-left: 12px;
  margin-left: -12px;
}
.sv-svc__item--ok { border-left-color: var(--ok); }
.sv-svc__item--error { border-left-color: var(--red); }
.sv-svc__item--unknown { border-left-color: var(--rule); }

.sv-svc__no {
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--red);
  font-variant-numeric: tabular-nums;
}
.sv-svc__main {}
.sv-svc__name {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--ink);
  letter-spacing: 0.15em;
}
.sv-svc__en {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  text-transform: uppercase;
  letter-spacing: var(--ls-wide);
  margin-top: 2px;
}
.sv-svc__detail {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-soft);
  letter-spacing: 0.05em;
}

.sv-cache { margin-top: var(--gap-5); }

.sv-cache__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gap-5);
}
.sv-cache__cell {
  border: 1px solid var(--rule);
  padding: var(--gap-4);
  background: var(--paper-deep);
}
.sv-cache__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px dashed var(--rule);
  padding-bottom: 8px;
  margin-bottom: 12px;
}
.sv-cache__zh {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--ink);
  letter-spacing: 0.18em;
}
.sv-cache__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0 0 var(--gap-3);
}
.sv-cache__meta > div {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px dotted var(--rule-fine);
  padding: 4px 0;
}
.sv-cache__meta dt {
  font-family: var(--serif);
  font-size: var(--fz-sm);
  color: var(--ink-mute);
  letter-spacing: 0.15em;
}
.sv-cache__meta dd {
  font-family: var(--mono);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--blue);
  margin: 0;
}
.sv-cache__meta dd small { color: var(--ink-mute); font-weight: 400; margin-left: 2px; }
</style>
