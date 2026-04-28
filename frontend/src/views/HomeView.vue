<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { systemApi, documentsApi } from '../api/client'
import {
  AppPageHead, AppMetricGrid, AppTag,
} from '../design/primitives'
import Icon from '../design/Icons.vue'

const health = ref<any>(null)
const docs = ref<any[]>([])

const stats = computed(() => [
  { label: '文档总数', value: docs.value.length, unit: '个' },
  { label: '页面总数', value: docs.value.reduce((s, d) => s + (d.total_pages || 0), 0), unit: '页' },
  { label: '已完成索引', value: docs.value.filter(d => d.status === 'completed').length, unit: '个' },
  { label: '索引失败', value: docs.value.filter(d => d.status === 'failed').length, unit: '个' },
])

const archSteps = [
  { id: '1', name: '上传',  en: 'INGEST',   icon: 'upload',  desc: 'PDF 文档上传，自动版面分析' },
  { id: '2', name: '索引',  en: 'INDEX',    icon: 'archive', desc: '页面切片，多模态向量化' },
  { id: '3', name: '检索',  en: 'RETRIEVE', icon: 'search',  desc: 'ColPali 视觉检索 + 重排序' },
  { id: '4', name: '生成',  en: 'GENERATE', icon: 'chat',    desc: 'LLM 生成回答，附引用来源' },
]

const services = computed(() => [
  {
    name: '后端服务',
    state: health.value ? 'ok' : 'unknown',
    detail: health.value ? '运行中' : '检测中',
  },
  {
    name: 'Worker 节点',
    state: health.value?.worker?.status === 'ok' ? 'ok' : (health.value ? 'error' : 'unknown'),
    detail: health.value?.worker?.model
      ? health.value.worker.model
      : (health.value?.worker?.status === 'ok' ? '就绪' : (health.value ? '未连接' : '检测中')),
  },
  {
    name: 'Qdrant 向量库',
    state: health.value?.qdrant?.status === 'ok' ? 'ok' : (health.value ? 'error' : 'unknown'),
    detail: health.value?.qdrant?.status === 'ok' ? '就绪' : (health.value ? '未连接' : '检测中'),
  },
])

function stateVar(s: string): 'ok' | 'red' | 'mute' {
  return ({ ok: 'ok', error: 'red', unknown: 'mute' } as const)[s as 'ok'] || 'mute'
}
function stateLabel(s: string) {
  return ({ ok: '正常', error: '异常', unknown: '检测中' } as Record<string,string>)[s] || s
}

const actions = [
  { to: '/chat',        icon: 'chat',    label: '多轮对话', en: 'Multi-turn Chat',     desc: '保留上下文，多轮追问，引用来源回填', primary: true, chap: '1' },
  { to: '/query',       icon: 'search',  label: '单次检索', en: 'Single-shot Query',   desc: '单次提问，展示检索结果与生成答案',                  chap: '2' },
  { to: '/documents',   icon: 'doc',     label: '文档管理', en: 'Document Management', desc: '上传 PDF，自动索引，支持删除与重试',                chap: '3' },
  { to: '/experiments', icon: 'flask',   label: '实验评测', en: 'Experiment & Eval',   desc: '切换 Pipeline，计算 Recall / MRR',             chap: '5' },
]

onMounted(async () => {
  try { const r = await systemApi.health(); health.value = r.data } catch {}
  try { const r = await documentsApi.list(); docs.value = r.data } catch {}
})
</script>

<template>
  <div class="hv">
    <AppPageHead
      chapter="0"
      kicker="系统概览"
      title="智能体检索增强系统"
      subtitle="面向多模态学术文献的版面感知检索与多轮对话框架，论文演示版"
      :meta="[
        { label: '系统', value: 'AGENTIC-RAG' },
        { label: '版本', value: 'v1.0' },
      ]"
      stamp="论文&#10;演示"
    />

    <AppMetricGrid :metrics="stats" :cols="4" class="hv__grid" />

    <section class="hv__sec">
      <header class="hv__sec-head">
        <span class="hv__sec-num">1</span>
        <h2 class="hv__sec-title">系统架构</h2>
        <p class="hv__sec-en">SYSTEM ARCHITECTURE</p>
      </header>
      <ol class="hv__arch">
        <template v-for="(s, i) in archSteps" :key="s.id">
          <li class="hv__arch-step">
            <div class="hv__arch-no">{{ s.id }}</div>
            <div class="hv__arch-icon">
              <Icon :name="s.icon" :size="22" />
            </div>
            <div class="hv__arch-name">{{ s.name }}</div>
            <div class="hv__arch-en">{{ s.en }}</div>
            <p class="hv__arch-desc">{{ s.desc }}</p>
          </li>
          <li v-if="i < archSteps.length - 1" class="hv__arch-sep" aria-hidden="true">
            <span class="hv__arch-line"></span>
            <Icon name="chevron-right" :size="14" class="hv__arch-arrow" />
            <span class="hv__arch-line"></span>
          </li>
        </template>
      </ol>
    </section>

    <section class="hv__sec hv__sec--two">
      <div>
        <header class="hv__sec-head">
          <span class="hv__sec-num">2</span>
          <h2 class="hv__sec-title">服务状态</h2>
        </header>
        <ul class="hv__svc">
          <li v-for="(s, i) in services" :key="i" class="hv__svc-item">
            <span class="hv__svc-no">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="hv__svc-name">{{ s.name }}</span>
            <span class="hv__svc-detail">{{ s.detail }}</span>
            <AppTag :variant="stateVar(s.state)" size="sm">{{ stateLabel(s.state) }}</AppTag>
          </li>
        </ul>
      </div>

      <div>
        <header class="hv__sec-head">
          <span class="hv__sec-num">3</span>
          <h2 class="hv__sec-title">快速入口</h2>
        </header>
        <div class="hv__act">
          <RouterLink
            v-for="a in actions"
            :key="a.to"
            :to="a.to"
            class="hv-act-card"
            :class="{ 'hv-act-card--primary': a.primary }"
          >
            <span class="hv-act-card__chap">第 {{ a.chap }} 节</span>
            <Icon :name="a.icon" :size="22" class="hv-act-card__icon" />
            <span class="hv-act-card__label">{{ a.label }}</span>
            <span class="hv-act-card__en">{{ a.en }}</span>
            <p class="hv-act-card__desc">{{ a.desc }}</p>
            <span class="hv-act-card__arrow"><Icon name="arrow-right" :size="13" /></span>
          </RouterLink>
        </div>
      </div>
    </section>

    <footer class="hv__foot">
      <span>AGENTIC-RAG · 论文演示版</span>
      <span class="hv__foot-mono">v1.0 · 2026</span>
    </footer>
  </div>
</template>

<style scoped>
.hv { max-width: 1280px; margin: 0 auto; }

.hv__grid { margin-bottom: var(--gap-7); }

.hv__sec {
  margin-top: var(--gap-7);
}
.hv__sec-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 8px;
  margin-bottom: var(--gap-5);
}
.hv__sec-num {
  font-family: var(--mono);
  font-weight: 900;
  font-size: var(--fz-h2);
  color: var(--red);
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.hv__sec-title {
  flex: 1;
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h2);
  color: var(--blue);
  margin: 0;
  letter-spacing: 0.05em;
}
.hv__sec-en {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.18em;
  margin: 0;
}

/* Arch flow */
.hv__arch {
  list-style: none;
  margin: 0; padding: 0;
  display: flex;
  align-items: stretch;
  gap: 0;
}
.hv__arch-step {
  flex: 1;
  background: var(--paper-deep);
  border: 1px solid var(--rule);
  padding: 18px 18px 14px;
  position: relative;
  display: flex;
  flex-direction: column;
}
.hv__arch-no {
  position: absolute;
  top: 8px; right: 10px;
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono);
  color: var(--red);
}
.hv__arch-icon {
  width: 44px; height: 44px;
  background: var(--blue);
  color: var(--paper);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  flex-shrink: 0;
}
.hv__arch-name {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--ink);
  letter-spacing: 0.2em;
  margin-bottom: 4px;
}
.hv__arch-en {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.2em;
  margin-bottom: 8px;
}
.hv__arch-desc {
  font-family: var(--serif);
  font-size: var(--fz-sm);
  color: var(--ink-soft);
  margin: 0;
  line-height: 1.6;
}

.hv__arch-sep {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 24px;
  flex-shrink: 0;
}
.hv__arch-line {
  width: 1px;
  flex: 1;
  background: var(--rule);
}
.hv__arch-arrow {
  color: var(--red);
  margin: 8px 0;
  transform: rotate(0deg);
}

/* Two-col */
.hv__sec--two {
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  gap: var(--gap-7);
}

/* Services */
.hv__svc { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--rule); }
.hv__svc-item {
  display: grid;
  grid-template-columns: 36px 1fr auto auto;
  gap: 10px;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px dotted var(--rule);
}
.hv__svc-no {
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono-sm);
  color: var(--red);
}
.hv__svc-name {
  font-family: var(--serif);
  font-weight: 600;
  color: var(--ink);
  letter-spacing: 0.05em;
}
.hv__svc-detail {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.05em;
}

/* Actions */
.hv__act {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gap-3);
}
.hv-act-card {
  position: relative;
  display: block;
  background: var(--paper);
  border: 1px solid var(--rule);
  padding: 14px 16px 16px;
  text-decoration: none;
  color: var(--ink);
  transition: all var(--dur-fast) var(--ease-paper);
  border-bottom: none;
}
.hv-act-card::after {
  content: '';
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 4px;
  background:
    linear-gradient(to bottom,
      var(--ink) 0, var(--ink) 1px,
      transparent 1px, transparent 3px,
      var(--rule) 3px, var(--rule) 4px);
}
.hv-act-card:hover {
  border-color: var(--red);
  background: var(--paper-deep);
  transform: translateY(-2px);
}
.hv-act-card--primary { border-color: var(--blue); border-width: 2px; }
.hv-act-card--primary::after {
  background:
    linear-gradient(to bottom,
      var(--blue) 0, var(--blue) 2px,
      transparent 2px, transparent 3px,
      var(--rule) 3px, var(--rule) 4px);
}

.hv-act-card__chap {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  font-weight: 700;
  color: var(--red);
  letter-spacing: 0.15em;
  display: block;
  margin-bottom: 4px;
}
.hv-act-card__icon {
  display: block;
  color: var(--blue);
  margin-bottom: 6px;
}
.hv-act-card--primary .hv-act-card__icon { color: var(--blue); }
.hv-act-card__label {
  display: block;
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--ink);
  letter-spacing: 0.05em;
  margin-bottom: 2px;
}
.hv-act-card__en {
  display: block;
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.hv-act-card__desc {
  margin: 0;
  font-family: var(--serif);
  font-size: var(--fz-sm);
  color: var(--ink-soft);
  line-height: 1.5;
  text-indent: 0;
}
.hv-act-card__arrow {
  position: absolute;
  top: 16px; right: 16px;
  color: var(--ink-mute);
  transition: color var(--dur-fast), transform var(--dur-fast);
}
.hv-act-card:hover .hv-act-card__arrow {
  color: var(--red);
  transform: translateX(3px);
}

.hv__foot {
  margin-top: var(--gap-8);
  padding: var(--gap-4) 0;
  border-top: 2px solid var(--ink);
  display: flex;
  justify-content: space-between;
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.18em;
}
.hv__foot-mono { font-variant-numeric: tabular-nums; }
</style>
