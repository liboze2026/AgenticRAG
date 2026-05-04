<script setup lang="ts">
import { ref, computed } from 'vue'
import { AppPageHead, AppCard, AppButton, AppTag } from '../../design/primitives'
import { labApi, type GraphResponse, type GraphNode } from '../../api/client'

const query = ref('')
const topK = ref(5)
const includeNeighbours = ref(true)
const loading = ref(false)
const data = ref<GraphResponse | null>(null)
const error = ref('')

async function run() {
  if (!query.value.trim()) {
    error.value = '请先输入问题'
    return
  }
  error.value = ''
  loading.value = true
  data.value = null
  try {
    const r = await labApi.graph(query.value, { topK: topK.value, includeNeighbours: includeNeighbours.value })
    data.value = r.data
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '请求失败'
  } finally {
    loading.value = false
  }
}

function pageKey(n: GraphNode) {
  return `${n.document_id}::p${n.page_number}`
}

// Group nodes by page for column layout
const byPage = computed(() => {
  const out: Record<string, { docId: string; page: number; nodes: GraphNode[] }> = {}
  if (!data.value) return out
  for (const n of data.value.nodes) {
    const key = pageKey(n)
    if (!out[key]) out[key] = { docId: n.document_id, page: n.page_number, nodes: [] }
    out[key].nodes.push(n)
  }
  // sort columns: seed pages first
  const seedKeys = new Set((data.value.seeds || []).map(s => `${s.document_id}::p${s.page_number}`))
  return Object.fromEntries(
    Object.entries(out).sort(([a], [b]) => {
      const aa = seedKeys.has(a) ? 0 : 1
      const bb = seedKeys.has(b) ? 0 : 1
      if (aa !== bb) return aa - bb
      return a.localeCompare(b)
    })
  )
})

const edgeStats = computed(() => {
  if (!data.value) return [] as { type: string; count: number }[]
  const out: Record<string, number> = {}
  for (const e of data.value.edges) {
    out[e.edge_type] = (out[e.edge_type] || 0) + 1
  }
  return Object.entries(out).map(([type, count]) => ({ type, count }))
})

const edgeTypeLabel: Record<string, string> = {
  caption_of: '图/表 ↔ 题注',
  heading_to_text: '标题 → 正文',
  cross_page_continuation: '跨页续表',
  text_to_figure_ref: '正文 → 图引用',
}

function nodeShort(n: GraphNode) {
  return n.text ? n.text.slice(0, 30) : `${n.element_type} #${n.element_index}`
}

function isSeed(docId: string, page: number) {
  if (!data.value) return false
  return data.value.seeds.some(s => s.document_id === docId && s.page_number === page)
}
</script>

<template>
  <div class="gr">
    <AppPageHead
      chapter="E"
      kicker="LAB · Phase 6"
      title="局部关系图增强"
      subtitle="在候选页 + 邻接页内推导 caption / heading / 跨页续表 / 正文-图引用 等关系边"
      :meta="[
        { label: '入口', value: 'POST /api/lab/graph' },
        { label: '依赖', value: '已索引的版面元数据' },
      ]"
      stamp="LAB&#10;关系图"
    />

    <AppCard class="gr__form">
      <div class="gr__form-row">
        <input v-model="query" class="gr__inp" type="text" placeholder="例如：财报中关于研发投入的图表" @keydown.enter="run" />
        <label class="gr__num"><span>top-k</span><input type="number" v-model.number="topK" min="1" max="20" /></label>
        <label class="gr__chk"><input type="checkbox" v-model="includeNeighbours" /> 包含 ±1 邻接页</label>
        <AppButton variant="primary" :loading="loading" @click="run">构建关系图</AppButton>
      </div>
      <p v-if="error" class="gr__err">{{ error }}</p>
    </AppCard>

    <AppCard v-if="data" class="gr__sum">
      <div class="gr__sum-grid">
        <div><span>种子页</span><strong>{{ data.seeds.length }}</strong></div>
        <div><span>节点</span><strong>{{ data.nodes.length }}</strong></div>
        <div><span>边</span><strong>{{ data.edges.length }}</strong></div>
        <div><span>检索 ms</span><strong>{{ data.timing_ms.retrieve_ms?.toFixed(0) ?? '–' }}</strong></div>
        <div><span>建图 ms</span><strong>{{ data.timing_ms.graph_build_ms?.toFixed(0) ?? '–' }}</strong></div>
      </div>
      <div class="gr__edge-stats">
        <AppTag v-for="s in edgeStats" :key="s.type" variant="blue" size="sm">
          {{ edgeTypeLabel[s.type] || s.type }} × {{ s.count }}
        </AppTag>
      </div>
      <p v-if="data.note" class="gr__note">{{ data.note }}</p>
    </AppCard>

    <section v-if="data && data.nodes.length" class="gr__cols">
      <article v-for="(g, key) in byPage" :key="key" class="gr__col" :class="{ 'gr__col--seed': isSeed(g.docId, g.page) }">
        <header>
          <AppTag :variant="isSeed(g.docId, g.page) ? 'red' : 'blue'" size="sm">页 {{ g.page }}</AppTag>
          <span class="gr__doc" :title="g.docId">{{ g.docId.slice(0, 8) }}</span>
        </header>
        <ul>
          <li v-for="n in g.nodes" :key="n.id" :class="['gr__node', `gr__node--${n.element_type}`]">
            <span class="gr__type">{{ n.element_type }}</span>
            <span class="gr__txt">{{ nodeShort(n) }}</span>
          </li>
        </ul>
      </article>
    </section>

    <AppCard v-if="data && data.edges.length" class="gr__edges">
      <h4>关系边 ({{ data.edges.length }})</h4>
      <table>
        <thead>
          <tr><th>类型</th><th>源</th><th>目标</th><th>分</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr v-for="(e, i) in data.edges" :key="i">
            <td><AppTag size="sm">{{ edgeTypeLabel[e.edge_type] || e.edge_type }}</AppTag></td>
            <td class="gr__id">{{ e.source }}</td>
            <td class="gr__id">{{ e.target }}</td>
            <td>{{ e.score.toFixed(2) }}</td>
            <td class="gr__note-cell">{{ e.note }}</td>
          </tr>
        </tbody>
      </table>
    </AppCard>

    <AppCard v-else-if="data && !data.nodes.length" class="gr__empty">
      <p>{{ data.note || '空图：候选页可能未存版面元数据' }}</p>
    </AppCard>
  </div>
</template>

<style scoped>
.gr { max-width: 1200px; margin: 0 auto; }

.gr__form { padding: var(--gap-4); margin-bottom: var(--gap-3); }
.gr__form-row { display: flex; align-items: center; gap: var(--gap-3); flex-wrap: wrap; }
.gr__inp {
  flex: 1; min-width: 280px;
  padding: 8px 10px; font-family: var(--serif);
  border: 1px solid var(--rule); background: var(--paper);
}
.gr__inp:focus { outline: 2px solid var(--blue); }
.gr__num, .gr__chk {
  display: flex; align-items: center; gap: 6px;
  font-family: var(--serif); font-size: var(--fz-sm); color: var(--ink-soft);
}
.gr__num input { width: 60px; padding: 6px 8px; border: 1px solid var(--rule); font-family: var(--mono); }
.gr__err { margin: 8px 0 0; color: var(--red); font-family: var(--mono); font-size: var(--fz-mono-sm); }

.gr__sum { padding: var(--gap-4); margin-bottom: var(--gap-3); }
.gr__sum-grid {
  display: grid; grid-template-columns: repeat(5, 1fr);
  gap: var(--gap-3); margin-bottom: 12px;
}
.gr__sum-grid > div { display: flex; flex-direction: column; gap: 4px; }
.gr__sum-grid span { font-family: var(--mono); font-size: 10px; color: var(--ink-mute); letter-spacing: 0.15em; }
.gr__sum-grid strong { font-family: var(--serif); font-weight: 700; font-size: var(--fz-h4); color: var(--ink); }
.gr__edge-stats { display: flex; gap: 8px; flex-wrap: wrap; }
.gr__note { margin: 8px 0 0; color: var(--ink-soft); font-family: var(--serif); font-size: var(--fz-sm); }

.gr__cols {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--gap-3); margin-bottom: var(--gap-3);
}
.gr__col {
  background: var(--paper); border: 1px solid var(--rule);
  padding: 12px; display: flex; flex-direction: column; gap: 8px;
}
.gr__col--seed { border-color: var(--red); }
.gr__col header { display: flex; align-items: center; gap: 8px; padding-bottom: 8px; border-bottom: 1px dotted var(--rule); }
.gr__doc { font-family: var(--mono); font-size: var(--fz-mono-sm); color: var(--ink-mute); }
.gr__col ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
.gr__node {
  font-family: var(--serif); font-size: var(--fz-sm);
  padding: 4px 6px; border-left: 3px solid var(--ink-mute);
  background: var(--paper-deep); display: flex; gap: 8px; align-items: center;
}
.gr__node--heading      { border-left-color: var(--red); }
.gr__node--figure       { border-left-color: var(--blue); }
.gr__node--table        { border-left-color: #b86614; }
.gr__node--text_block   { border-left-color: var(--ink-mute); }
.gr__type { font-family: var(--mono); font-size: 10px; color: var(--ink-mute); flex-shrink: 0; }
.gr__txt  { color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.gr__edges { padding: var(--gap-4); }
.gr__edges h4 { margin: 0 0 12px; font-family: var(--serif); color: var(--blue); letter-spacing: 0.15em; }
.gr__edges table { width: 100%; border-collapse: collapse; font-family: var(--serif); font-size: var(--fz-sm); }
.gr__edges th, .gr__edges td { padding: 6px 10px; border-bottom: 1px dotted var(--rule); text-align: left; vertical-align: top; }
.gr__edges th { font-weight: 700; color: var(--ink-mute); letter-spacing: 0.1em; font-size: 11px; }
.gr__id { font-family: var(--mono); font-size: var(--fz-mono-sm); color: var(--ink-soft); word-break: break-all; }
.gr__note-cell { color: var(--ink-soft); }

.gr__empty { padding: var(--gap-4); text-align: center; color: var(--ink-soft); }
</style>
