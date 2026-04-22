<template>
  <div class="home-view">
    <!-- Hero -->
    <div class="home-hero">
      <div class="home-hero__badge">硕士学位论文系统演示</div>
      <div class="home-hero__title">多模态 Agentic RAG 系统</div>
      <div class="home-hero__subtitle">基于版面理解的检索增强生成平台 · 支持多策略检索与多模型生成</div>
    </div>

    <!-- Architecture Flow -->
    <div class="arch-flow">
      <div class="arch-flow__label">系统架构</div>
      <div class="arch-flow__steps">
        <div class="arch-step" v-for="(step, i) in archSteps" :key="step.name">
          <div class="arch-step__box">
            <svg class="arch-step__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" v-html="step.svg" />
            <span class="arch-step__name">{{ step.name }}</span>
          </div>
          <div v-if="i < archSteps.length - 1" class="arch-step__arrow">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
          </div>
        </div>
      </div>
    </div>

    <!-- Stats -->
    <div class="home-stats-row">
      <div class="stat-card" v-for="stat in stats" :key="stat.label">
        <div class="stat-card__value" :style="{ color: stat.color }">{{ stat.value }}</div>
        <div class="stat-card__label">{{ stat.label }}</div>
        <div class="stat-card__desc">{{ stat.desc }}</div>
      </div>
    </div>

    <!-- Service Status -->
    <div class="home-section-title">服务状态</div>
    <div class="home-status-row">
      <div v-for="svc in services" :key="svc.label" class="status-card" :class="`status-card--${svc.state}`">
        <div class="status-dot" :class="`dot--${svc.state}`" />
        <div class="status-card__body">
          <div class="status-card__label">{{ svc.label }}</div>
          <div class="status-card__state">{{ svc.stateText }}</div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="home-section-title">快速操作</div>
    <div class="home-actions__grid">
      <router-link to="/documents" class="action-card">
        <div class="action-card__header">
          <svg class="action-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          <span class="action-card__label">上传文档</span>
        </div>
        <div class="action-card__desc">上传 PDF，自动版面分析与向量索引</div>
      </router-link>
      <router-link to="/chat" class="action-card action-card--primary">
        <div class="action-card__header">
          <svg class="action-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <span class="action-card__label">智能对话</span>
        </div>
        <div class="action-card__desc">多轮对话，RAG 检索增强生成</div>
      </router-link>
      <router-link to="/query" class="action-card">
        <div class="action-card__header">
          <svg class="action-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <span class="action-card__label">检索问答</span>
        </div>
        <div class="action-card__desc">单次问答，查看检索溯源链路</div>
      </router-link>
      <router-link to="/experiments" class="action-card">
        <div class="action-card__header">
          <svg class="action-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          <span class="action-card__label">实验评测</span>
        </div>
        <div class="action-card__desc">切换检索策略，评估 Recall / MRR</div>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { systemApi, documentsApi } from '../api/client'

const health = ref<any>(null)
const docs = ref<any[]>([])

const archSteps = [
  { name: '文档上传', svg: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>' },
  { name: '版面分析', svg: '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="9" x2="9" y2="21"/>' },
  { name: '向量索引', svg: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>' },
  { name: 'Agentic 检索', svg: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>' },
  { name: '智能生成', svg: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>' },
]

const services = computed(() => [
  {
    label: 'Backend API',
    state: health.value ? 'ok' : 'unknown',
    stateText: health.value ? '运行中' : '检测中…',
  },
  {
    label: 'Worker (ColPali)',
    state: health.value?.worker?.status === 'ok' ? 'ok' : 'error',
    stateText: health.value?.worker?.model || (health.value?.worker?.status === 'ok' ? '就绪' : '未连接'),
  },
  {
    label: 'Qdrant 向量库',
    state: health.value?.qdrant?.status === 'ok' ? 'ok' : 'error',
    stateText: health.value?.qdrant?.status === 'ok' ? '就绪' : '未连接',
  },
])

const stats = computed(() => [
  { value: docs.value.length, label: '已上传文档', desc: 'PDF 文档总数', color: 'var(--accent)' },
  { value: docs.value.reduce((s, d) => s + (d.total_pages || 0), 0), label: '总页面数', desc: '已索引页面', color: '#0891b2' },
  { value: docs.value.filter(d => d.status === 'completed').length, label: '完成索引', desc: '可供检索', color: 'var(--success)' },
  { value: docs.value.filter(d => d.status === 'failed').length, label: '索引失败', desc: '需重试', color: 'var(--danger)' },
])

onMounted(async () => {
  try { const r = await systemApi.health(); health.value = r.data } catch {}
  try { const r = await documentsApi.list(); docs.value = r.data } catch {}
})
</script>

<style scoped>
.home-view { max-width: 1100px; margin: 0 auto; }

/* Hero */
.home-hero { text-align: center; padding: 32px 0 28px; }
.home-hero__badge {
  display: inline-block;
  background: var(--accent-light);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  padding: 3px 12px;
  border-radius: 20px;
  border: 1px solid #bfdbfe;
  margin-bottom: 14px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.home-hero__title {
  font-size: 30px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  line-height: 1.2;
  margin-bottom: 10px;
}
.home-hero__subtitle {
  font-size: 14px;
  color: var(--text-muted);
}

/* Architecture flow */
.arch-flow {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-sm);
}
.arch-flow__label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 12px;
}
.arch-flow__steps {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.arch-step { display: flex; align-items: center; gap: 6px; }
.arch-step__box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--accent-light);
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
}
.arch-step__icon { width: 16px; height: 16px; flex-shrink: 0; }
.arch-step__arrow { width: 20px; color: var(--text-muted); }
.arch-step__arrow svg { width: 16px; height: 16px; }

/* Stats */
.home-stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}
.stat-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  box-shadow: var(--shadow-sm);
}
.stat-card__value {
  font-size: 36px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.stat-card__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-top: 6px;
}
.stat-card__desc {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* Section titles */
.home-section-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 10px;
  margin-top: 4px;
}

/* Service status */
.home-status-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 24px;
}
.status-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: var(--shadow-sm);
}
.status-card--ok { border-left: 3px solid var(--success); }
.status-card--error { border-left: 3px solid var(--danger); }
.status-card--unknown { border-left: 3px solid var(--text-muted); }

.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot--ok { background: var(--success); box-shadow: 0 0 0 3px var(--success-light); }
.dot--error { background: var(--danger); box-shadow: 0 0 0 3px var(--danger-light); }
.dot--unknown { background: var(--text-muted); }

.status-card__label { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.status-card__state { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

/* Actions */
.home-actions__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.action-card {
  background: var(--bg-surface);
  border: 1.5px solid var(--border);
  border-radius: 8px;
  padding: 18px 16px;
  text-decoration: none;
  display: block;
  transition: border-color .2s, transform .15s, box-shadow .2s;
  box-shadow: var(--shadow-sm);
}
.action-card:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.action-card--primary {
  border-color: var(--accent);
  background: var(--accent-light);
}
.action-card__header { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.action-card__icon { width: 20px; height: 20px; color: var(--accent); flex-shrink: 0; }
.action-card__label { font-size: 14px; font-weight: 700; color: var(--text-primary); }
.action-card__desc { font-size: 12px; color: var(--text-muted); line-height: 1.5; }
</style>
