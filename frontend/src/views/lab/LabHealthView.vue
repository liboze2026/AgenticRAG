<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { AppPageHead, AppCard, AppButton, AppTag } from '../../design/primitives'
import { labApi, type LabHealth, type LabInfo } from '../../api/client'

const loading = ref(false)
const health = ref<LabHealth | null>(null)
const info = ref<LabInfo | null>(null)
const error = ref('')

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [h, i] = await Promise.all([labApi.health(), labApi.info()])
    health.value = h.data
    info.value = i.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}
onMounted(refresh)

interface Check {
  name: string
  ok: boolean
  detail: string
  blocking: boolean
}

const checks = computed<Check[]>(() => {
  const h = health.value
  if (!h) return []
  return [
    { name: '主 Pipeline', ok: h.main_pipeline_ok, detail: h.main_pipeline_ok ? '已就绪' : 'Qdrant / Worker 未连通', blocking: true },
    { name: '已索引文档 (layout)', ok: h.layout_ready, detail: h.layout_ready ? '至少 1 篇已索引' : '未发现已完成索引的文档', blocking: true },
    { name: 'BM25 索引', ok: h.bm25_ready, detail: h.bm25_ready ? `${h.bm25_doc_count} 页` : '将于首次双通道查询时同步', blocking: false },
    { name: 'sklearn (GMM)', ok: h.sklearn_available, detail: h.sklearn_available ? 'GaussianMixture 可用' : '未安装 — Phase 3 退化为固定 top-k', blocking: false },
    { name: '区域级集合', ok: h.region_collection_ready, detail: h.region_collection_ready ? `${h.region_point_count} 个区域点` : '未索引 — 在 [区域级检索] 页可触发', blocking: false },
  ]
})
</script>

<template>
  <div class="hh">
    <AppPageHead
      chapter="L"
      kicker="LAB · 状态"
      title="实验台状态"
      subtitle="一览 4 个 Lab 模块的就绪情况，预先暴露阻塞项 — 演示前最后一道检查"
      :meta="[
        { label: '入口', value: '/api/lab/health' },
      ]"
      stamp="LAB&#10;就绪"
    />

    <div class="hh__bar">
      <AppButton variant="primary" :loading="loading" @click="refresh">刷新检测</AppButton>
    </div>

    <div v-if="error" class="hh__err">{{ error }}</div>

    <section v-if="checks.length" class="hh__grid">
      <article v-for="c in checks" :key="c.name" class="hh__check"
        :class="{ 'hh__check--ok': c.ok, 'hh__check--bad': !c.ok && c.blocking, 'hh__check--warn': !c.ok && !c.blocking }">
        <header class="hh__check-h">
          <span class="hh__icon">{{ c.ok ? '✓' : (c.blocking ? '✗' : '!') }}</span>
          <h4>{{ c.name }}</h4>
        </header>
        <p>{{ c.detail }}</p>
        <span class="hh__pill">{{ c.blocking ? '关键' : '非阻塞' }}</span>
      </article>
    </section>

    <AppCard v-if="health?.notes.length" class="hh__notes">
      <h4>提示</h4>
      <ul>
        <li v-for="(n, i) in health.notes" :key="i">{{ n }}</li>
      </ul>
    </AppCard>

    <AppCard v-if="info" class="hh__phases">
      <h4>已挂载的 Lab 模块</h4>
      <ul class="hh__phase-list">
        <li v-for="p in info.phases" :key="p.id">
          <div class="hh__phase-h">
            <AppTag variant="blue" size="sm">{{ p.id.toUpperCase() }}</AppTag>
            <strong>{{ p.title }}</strong>
            <span class="hh__ep">{{ p.method }} {{ p.endpoint }}</span>
          </div>
          <p>{{ p.desc }}</p>
        </li>
      </ul>
    </AppCard>
  </div>
</template>

<style scoped>
.hh { max-width: 1100px; margin: 0 auto; }
.hh__bar { margin-bottom: var(--gap-4); }
.hh__err {
  padding: 12px 16px; margin-bottom: var(--gap-3);
  background: #fff5f5; border: 1px solid var(--red); color: var(--red);
  font-family: var(--mono); font-size: var(--fz-mono-sm);
}

.hh__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--gap-3);
  margin-bottom: var(--gap-4);
}
.hh__check {
  position: relative;
  padding: 14px 16px;
  background: var(--paper); border: 1px solid var(--rule);
  border-top: 3px solid var(--ink-mute);
  display: flex; flex-direction: column; gap: 8px;
}
.hh__check--ok   { border-top-color: #2d7a4d; }
.hh__check--bad  { border-top-color: var(--red); }
.hh__check--warn { border-top-color: #b86614; }
.hh__check-h { display: flex; align-items: center; gap: 10px; }
.hh__icon {
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-weight: 800;
  background: var(--ink-mute); color: var(--paper);
  font-size: 16px;
}
.hh__check--ok   .hh__icon { background: #2d7a4d; }
.hh__check--bad  .hh__icon { background: var(--red); }
.hh__check--warn .hh__icon { background: #b86614; }
.hh__check h4 {
  margin: 0; flex: 1;
  font-family: var(--serif); font-weight: 700;
  font-size: var(--fz-h4); color: var(--ink);
  letter-spacing: 0.15em;
}
.hh__check p {
  margin: 0; font-family: var(--serif);
  font-size: var(--fz-sm); color: var(--ink-soft);
  line-height: 1.55;
}
.hh__pill {
  align-self: flex-start;
  font-family: var(--mono); font-size: 10px;
  color: var(--ink-mute); letter-spacing: 0.15em;
  border: 1px dotted var(--rule);
  padding: 2px 6px;
}

.hh__notes { padding: var(--gap-4); margin-bottom: var(--gap-3); }
.hh__notes h4 { margin: 0 0 8px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.hh__notes ul { padding-left: 24px; margin: 0; }
.hh__notes li { font-family: var(--serif); line-height: 1.7; color: var(--ink-soft); margin: 4px 0; }

.hh__phases { padding: var(--gap-4); }
.hh__phases h4 { margin: 0 0 12px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.18em; }
.hh__phase-list { list-style: none; padding: 0; margin: 0; }
.hh__phase-list li {
  border-bottom: 1px dotted var(--rule);
  padding: 12px 0;
}
.hh__phase-list li:last-child { border-bottom: none; }
.hh__phase-h { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.hh__phase-h strong {
  font-family: var(--serif); color: var(--ink);
  letter-spacing: 0.1em; font-size: var(--fz-sm);
}
.hh__ep {
  margin-left: auto;
  font-family: var(--mono); font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
}
.hh__phase-list p {
  margin: 6px 0 0; font-family: var(--serif);
  font-size: var(--fz-sm); color: var(--ink-soft); line-height: 1.6;
}
</style>
