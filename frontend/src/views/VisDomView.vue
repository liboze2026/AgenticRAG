<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  AppPageHead, AppCard, AppMetricGrid, AppTable, AppTag, AppEmpty, AppButton,
} from '../design/primitives'
import Icon from '../design/Icons.vue'

interface PerQuery {
  q_id: string
  query: string
  target_doc: string
  reference_figure?: string
  paper_title?: string
  retrieved_unique_ordered: string[]
  retrieved_pages: { doc_id: string; page: number; score: number }[]
  rr: number
  recall_at_k: Record<string, number>
  timing_ms: Record<string, number>
}
interface Result {
  manifest: {
    dataset: string
    subset_strategy: string
    papers: string[]
    doc_pages: Record<string, number>
    queries_total_in_subset: number
    queries_in_eval: number
    csv_source: string
    pdf_source: string
  }
  papers_meta?: Record<string, { pages: number }>
  metrics: {
    [k: string]: any
    mrr: number
    n_queries: number
    avg_timing_ms: Record<string, number>
  }
  per_query: PerQuery[]
}

const data = ref<Result | null>(null)
const loading = ref(true)
const errorMsg = ref('')
const focusIdx = ref(0)

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const r = await fetch(`/visdom/results.json?t=${Date.now()}`)
    if (!r.ok) throw new Error(`${r.status}`)
    data.value = await r.json()
  } catch (e: any) {
    errorMsg.value = `结果文件未生成或无法读取：${e?.message || e}。请先运行 scripts/visdom_run.py。`
  } finally {
    loading.value = false
  }
}

onMounted(load)

const metricCells = computed(() => {
  if (!data.value) return []
  const m = data.value.metrics
  return [
    { label: 'Recall@1', value: (m['recall@1'] || 0).toFixed(4) },
    { label: 'Recall@5', value: (m['recall@5'] || 0).toFixed(4) },
    { label: 'Recall@10', value: (m['recall@10'] || 0).toFixed(4) },
    { label: 'MRR', value: m.mrr.toFixed(4) },
  ]
})

const corpusRows = computed(() => {
  if (!data.value) return []
  return data.value.manifest.papers.map((arxiv) => ({
    arxiv,
    pages: data.value!.manifest.doc_pages[arxiv] || data.value!.papers_meta?.[arxiv]?.pages || 0,
    queries: data.value!.per_query.filter(q => q.target_doc === arxiv).length,
    perDocRecall1: docRecall(arxiv, 1),
    perDocRecall5: docRecall(arxiv, 5),
  }))
})

function docRecall(arxiv: string, k: number) {
  if (!data.value) return 0
  const qs = data.value.per_query.filter(q => q.target_doc === arxiv)
  if (!qs.length) return 0
  const hit = qs.filter(q => (q.recall_at_k[String(k)] ?? 0) > 0).length
  return hit / qs.length
}

const corpusCols = [
  { key: 'arxiv', label: 'arXiv ID', width: '160px' },
  { key: 'pages', label: '页数', width: '80px', numeric: true },
  { key: 'queries', label: '相关查询', width: '90px', numeric: true },
  { key: 'perDocRecall1', label: 'R@1', width: '80px', numeric: true },
  { key: 'perDocRecall5', label: 'R@5', width: '80px', numeric: true },
]

const focused = computed(() => data.value?.per_query[focusIdx.value] || null)
const targetDocRank = computed(() => {
  if (!focused.value) return 0
  const idx = focused.value.retrieved_unique_ordered.indexOf(focused.value.target_doc)
  return idx === -1 ? 0 : idx + 1
})
const targetInPageTop10 = computed(() => {
  if (!focused.value) return false
  return focused.value.retrieved_pages.some(p => p.doc_id === focused.value!.target_doc)
})

const histogramByRank = computed(() => {
  if (!data.value) return [] as number[]
  const buckets = [0, 0, 0, 0, 0, 0]   // ranks 1-5, miss
  for (const q of data.value.per_query) {
    const idx = q.retrieved_unique_ordered.indexOf(q.target_doc)
    if (idx === -1) buckets[5]++
    else buckets[Math.min(idx, 4)]++
  }
  return buckets
})

function pageImg(arxiv: string, page: number) {
  return `/visdom/pages/${arxiv}/page_${page}.png`
}
</script>

<template>
  <div class="vd">
    <AppPageHead
      chapter="X"
      kicker="VisDoM 复现实验"
      title="VisDoM · SPIQA 子集检索复现"
      :subtitle="data
        ? `基于 ColPali 视觉检索流水线，在 SPIQA 子集（${data.manifest.papers.length} 篇论文 / ${data.manifest.queries_in_eval} 个查询）上复现 VisDoM 论文的视觉检索环节`
        : '基于 ColPali 视觉检索流水线，在 SPIQA 子集上复现 VisDoM 论文的视觉检索环节'"
      :meta="[
        { label: '原文', value: 'arXiv:2412.10704' },
        { label: 'NAACL', value: '2025' },
      ]"
      stamp="检索&#10;复现"
    />

    <div class="vd__bar">
      <AppButton variant="ghost" size="sm" @click="load">
        <Icon name="reload" :size="13" />
        重新加载
      </AppButton>
      <a class="vd__src" href="https://github.com/MananSuri27/VisDoM/" target="_blank" rel="noopener">
        <Icon name="book" :size="13" /> 原仓库
      </a>
      <a class="vd__src" href="https://arxiv.org/abs/2412.10704" target="_blank" rel="noopener">
        <Icon name="doc" :size="13" /> 原论文 arXiv
      </a>
    </div>

    <AppEmpty v-if="loading" text="加载结果中⋯" hint="please wait" />
    <AppCard v-else-if="errorMsg" title="结果未就绪" :num="'!'">
      <p class="vd__err">{{ errorMsg }}</p>
      <pre class="vd__cmd">cd D:/0/agentic_rag/AgenticRAG
.venv/Scripts/python.exe scripts/visdom_run.py</pre>
    </AppCard>

    <template v-else-if="data">

      <!-- 1. 原理 -->
      <section class="vd__sec">
        <header class="vd__sec-head">
          <span class="vd__sec-num">1</span>
          <h2 class="vd__sec-title">实验原理</h2>
          <p class="vd__sec-en">METHOD · VISUAL RETRIEVAL FOR MULTIMODAL RAG</p>
        </header>
        <div class="vd__principle">
          <div class="vd__principle-cell">
            <div class="vd__principle-label">问题</div>
            <p>多模态长文档（包含表格、图表、幻灯片）上的检索增强生成（Multi-Doc QA with Visually Rich Elements）。
            纯文本 RAG 切片会丢失版面和视觉信息，影响对图表/表格相关问题的检索召回。</p>
          </div>
          <div class="vd__principle-cell">
            <div class="vd__principle-label">方法</div>
            <p>VisDoMRAG 使用<b>视觉检索器（ColPali / ColQwen）</b>对页面截图编码为 patch-level 多向量，结合
            <b>文本检索器（BM25 / MiniLM / MPNet / BGE）</b>，对每个查询从候选文档中召回 Top-K 相关页面。检索结果分别送入
            视觉模型与文本模型生成回答，最后融合两路答案。</p>
          </div>
          <div class="vd__principle-cell">
            <div class="vd__principle-label">本次复现范围</div>
            <p>仅复现 VisDoMRAG 的<b>视觉检索环节</b>（ColPali 多向量编码 + MaxSim 相似度），
            不复现 LLM 答案生成与跨模态融合。评估指标限定于检索性能：
            <code>Recall@K</code> 与 <code>MRR</code>，按目标文档（doc-level）匹配，K ∈ {1, 3, 5, 10}。</p>
          </div>
        </div>
      </section>

      <!-- 2. 过程 -->
      <section class="vd__sec">
        <header class="vd__sec-head">
          <span class="vd__sec-num">2</span>
          <h2 class="vd__sec-title">实验过程</h2>
          <p class="vd__sec-en">PROCEDURE · CORPUS &amp; PIPELINE</p>
        </header>

        <div class="vd__proc-grid">
          <div class="vd__proc-cell">
            <div class="vd__proc-l">数据来源</div>
            <div class="vd__proc-v">VisDoMBench / SPIQA 子集</div>
            <div class="vd__proc-h">Scientific Papers · Tables &amp; Charts</div>
          </div>
          <div class="vd__proc-cell">
            <div class="vd__proc-l">采样策略</div>
            <div class="vd__proc-v">{{ data.manifest.subset_strategy }}</div>
            <div class="vd__proc-h">论文数 {{ data.manifest.papers.length }} · 查询数 {{ data.manifest.queries_in_eval }}</div>
          </div>
          <div class="vd__proc-cell">
            <div class="vd__proc-l">视觉检索器</div>
            <div class="vd__proc-v">ColPali v1.2</div>
            <div class="vd__proc-h">页面截图 → patch 多向量</div>
          </div>
          <div class="vd__proc-cell">
            <div class="vd__proc-l">相似度</div>
            <div class="vd__proc-v">MaxSim</div>
            <div class="vd__proc-h">多向量逐 token 取最大点积后求和</div>
          </div>
        </div>

        <h3 class="vd__sub">2.1 语料组成</h3>
        <AppTable :columns="corpusCols" :rows="corpusRows">
          <template #cell-arxiv="{ row }">
            <a class="vd__arxiv" :href="`https://arxiv.org/abs/${row.arxiv.replace(/v\d+$/, '')}`" target="_blank" rel="noopener">
              {{ row.arxiv }}
            </a>
          </template>
          <template #cell-perDocRecall1="{ row }">{{ (row.perDocRecall1 as number).toFixed(3) }}</template>
          <template #cell-perDocRecall5="{ row }">{{ (row.perDocRecall5 as number).toFixed(3) }}</template>
        </AppTable>

        <h3 class="vd__sub">2.2 流水线步骤</h3>
        <ol class="vd__steps">
          <li><b>选取数据子集</b>：在 SPIQA 全集 117 篇论文 / 586 个查询中，按查询数排序取前 {{ data.manifest.papers.length }} 篇论文及其对应查询。</li>
          <li><b>页面渲染</b>：在远程 GPU 服务器本地用 pdf2image 将每篇 PDF 转为 150 DPI PNG 截图（{{ Object.values(data.manifest.doc_pages).reduce((a, b) => a + (b as number), 0) }} 页）。</li>
          <li><b>视觉编码</b>：将每页截图通过 <code>POST /encode/documents</code> 送入 ColPali worker（GPU 1，RTX 3090），得到 patch-level 多向量嵌入。</li>
          <li><b>查询编码</b>：将每个文本查询通过 <code>POST /encode/query</code> 送入 ColPali，得到 query token 多向量。</li>
          <li><b>MaxSim 检索</b>：对每个查询，与所有页面计算 MaxSim 相似度（每个 query token 取 patch 最大点积，然后求和），按分数降序取 Top-10。</li>
          <li><b>doc-level 评测</b>：在 Top-K 中按 doc_id 去重保序后，检查目标论文是否在 Top-1/3/5/10，统计 Recall@K + MRR。</li>
        </ol>
      </section>

      <!-- 3. 结果 -->
      <section class="vd__sec">
        <header class="vd__sec-head">
          <span class="vd__sec-num">3</span>
          <h2 class="vd__sec-title">实验结果</h2>
          <p class="vd__sec-en">RESULTS · DOC-LEVEL RECALL &amp; MRR</p>
        </header>

        <AppMetricGrid :metrics="metricCells" :cols="4" />

        <h3 class="vd__sub">3.1 命中排名分布</h3>
        <p class="vd__hint">目标论文在 Top-10 中第几位被命中（横轴），命中查询数（纵轴）。</p>
        <div class="vd__hist">
          <div v-for="(c, i) in histogramByRank" :key="i" class="vd__hist-bar">
            <div
              class="vd__hist-fill"
              :style="{ height: (c / Math.max(...histogramByRank)) * 100 + '%' }"
              :title="`${c} 个查询`"
            ></div>
            <div class="vd__hist-c">{{ c }}</div>
            <div class="vd__hist-l">{{ i < 5 ? `Rank ${i+1}` : '未命中' }}</div>
          </div>
        </div>

        <h3 class="vd__sub">3.2 平均耗时分解</h3>
        <ul class="vd__timing">
          <li v-for="(v, k) in data.metrics.avg_timing_ms" :key="k">
            <span class="vd__timing-l">{{ k }}</span>
            <span class="vd__timing-v">{{ (v as number).toFixed(0) }}<small> ms</small></span>
          </li>
        </ul>
      </section>

      <!-- 4. 单查询样例 -->
      <section class="vd__sec">
        <header class="vd__sec-head">
          <span class="vd__sec-num">4</span>
          <h2 class="vd__sec-title">单查询样例</h2>
          <p class="vd__sec-en">QUERY DRILL-DOWN · TOP-10 PAGES</p>
        </header>

        <div class="vd__nav">
          <AppButton size="sm" variant="ghost" :disabled="focusIdx === 0" @click="focusIdx = Math.max(0, focusIdx - 1)">
            <Icon name="chevron-left" :size="13" />
            上一查询
          </AppButton>
          <span class="vd__nav-no">{{ focusIdx + 1 }} / {{ data.per_query.length }}</span>
          <AppButton size="sm" variant="ghost" :disabled="focusIdx === data.per_query.length - 1" @click="focusIdx = Math.min(data.per_query.length - 1, focusIdx + 1)">
            下一查询
            <Icon name="chevron-right" :size="13" />
          </AppButton>
        </div>

        <div v-if="focused" class="vd__qa">
          <div class="vd__q">
            <span class="vd__q-seal">问</span>
            <div>
              <p class="vd__q-text">{{ focused.query }}</p>
              <div class="vd__q-meta">
                <span><b>{{ focused.q_id }}</b></span>
                <span>目标论文 <code>{{ focused.target_doc }}</code></span>
                <span>RR <b>{{ focused.rr.toFixed(3) }}</b></span>
                <AppTag :variant="(focused.recall_at_k['5'] ?? 0) > 0 ? 'ok' : 'red'" size="sm">
                  {{ (focused.recall_at_k['5'] ?? 0) > 0 ? 'Top-5 命中' : 'Top-5 未中' }}
                </AppTag>
              </div>
            </div>
          </div>

          <h4 class="vd__hits-h">
            检索到的 Top-10 页面
            <span v-if="targetDocRank > 0" class="vd__hits-note">
              · 目标论文文档级排名 第 {{ targetDocRank }} 位
              <span v-if="!targetInPageTop10">（目标论文最高分页面排在 page-level Top-10 之外）</span>
            </span>
            <span v-else class="vd__hits-note vd__hits-note--miss">
              · 目标论文未进入 Top-10 文档
            </span>
          </h4>
          <div class="vd__hits">
            <div
              v-for="(p, i) in focused.retrieved_pages"
              :key="i"
              class="vd__hit"
              :class="{ 'vd__hit--target': p.doc_id === focused.target_doc }"
            >
              <div class="vd__hit-rank">{{ i + 1 }}</div>
              <img :src="pageImg(p.doc_id, p.page)" :alt="`${p.doc_id} page ${p.page}`" />
              <div class="vd__hit-meta">
                <span class="vd__hit-page">{{ p.doc_id.slice(0, 10) }} · 第 {{ p.page }} 页</span>
                <span class="vd__hit-score">{{ p.score.toFixed(2) }}</span>
              </div>
              <div v-if="p.doc_id === focused.target_doc" class="vd__hit-tag">目标</div>
            </div>
          </div>
        </div>
      </section>

      <footer class="vd__foot">
        <span>VisDoM 复现 · {{ data.metrics.n_queries }} 个查询 · {{ data.manifest.papers.length }} 篇论文</span>
        <span class="vd__foot-mono">recall@5 = {{ (data.metrics['recall@5'] || 0).toFixed(4) }}</span>
      </footer>
    </template>
  </div>
</template>

<style scoped>
.vd { max-width: 1280px; margin: 0 auto; }

.vd__bar {
  display: flex;
  align-items: center;
  gap: var(--gap-3);
  padding: 8px 0 var(--gap-5);
  border-bottom: 1px dashed var(--rule);
  margin-bottom: var(--gap-5);
}
.vd__src {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--blue);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  letter-spacing: 0.05em;
}
.vd__src:hover { border-bottom-color: var(--red); color: var(--red); }

.vd__err { color: var(--red); font-family: var(--serif); margin: 0 0 var(--gap-3); }
.vd__cmd {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  background: var(--paper-deep);
  border: 1px solid var(--rule);
  padding: 10px 12px;
  margin: 0;
  color: var(--ink);
}

/* === Sections === */
.vd__sec { margin-top: var(--gap-7); }
.vd__sec-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 8px;
  margin-bottom: var(--gap-5);
}
.vd__sec-num {
  font-family: var(--mono);
  font-weight: 900;
  font-size: var(--fz-h2);
  color: var(--red);
  line-height: 1;
}
.vd__sec-title {
  flex: 1;
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h2);
  color: var(--blue);
  margin: 0;
  letter-spacing: 0.05em;
}
.vd__sec-en {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.18em;
  margin: 0;
}
.vd__sub {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--blue);
  margin: var(--gap-5) 0 var(--gap-3);
  letter-spacing: 0.1em;
}

/* === 1. Principle === */
.vd__principle {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--gap-4);
}
.vd__principle-cell {
  background: var(--paper-deep);
  border: 1px solid var(--rule);
  padding: 14px 16px;
}
.vd__principle-label {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--red);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.vd__principle-cell p {
  font-family: var(--serif);
  font-size: var(--fz-sm);
  color: var(--ink);
  line-height: 1.7;
  margin: 0;
  text-indent: 0;
}
.vd__principle-cell code {
  font-family: var(--mono);
  font-size: 12px;
  background: var(--paper);
  border: 1px solid var(--rule-fine);
  padding: 0 4px;
}

/* === 2. Procedure === */
.vd__proc-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  border: 1px solid var(--ink);
  margin-bottom: var(--gap-5);
}
.vd__proc-cell {
  padding: 14px 18px;
  border-right: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  background: var(--paper);
}
.vd__proc-cell:last-child { border-right: none; }
.vd__proc-l {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.vd__proc-v {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--blue);
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}
.vd__proc-h {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
}

.vd__steps {
  list-style: none;
  margin: 0; padding: 0;
  counter-reset: vds;
}
.vd__steps li {
  counter-increment: vds;
  position: relative;
  font-family: var(--serif);
  font-size: var(--fz-sm);
  color: var(--ink);
  padding: 12px 16px 12px 56px;
  border-bottom: 1px dotted var(--rule);
  line-height: 1.7;
}
.vd__steps li::before {
  content: counter(vds, decimal-leading-zero);
  position: absolute;
  left: 16px; top: 12px;
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono);
  color: var(--red);
  background: var(--paper-deep);
  border: 1px solid var(--rule);
  padding: 1px 8px;
}
.vd__steps li code {
  font-family: var(--mono);
  font-size: 12px;
  background: var(--paper-deep);
  border: 1px solid var(--rule-fine);
  padding: 0 4px;
}

.vd__arxiv {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--blue);
  border-bottom: 1px dotted var(--blue);
}

/* === 3. Results === */
.vd__hint {
  font-family: var(--serif);
  font-style: italic;
  font-size: var(--fz-sm);
  color: var(--ink-mute);
  margin: 0 0 var(--gap-3);
}
.vd__hist {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--gap-3);
  border: 1px solid var(--rule);
  background: var(--paper);
  padding: 16px;
  align-items: end;
  height: 220px;
}
.vd__hist-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  position: relative;
}
.vd__hist-fill {
  width: 60%;
  background: linear-gradient(to top, var(--red) 0%, var(--red) 80%, var(--red-soft) 100%);
  margin-top: auto;
  transition: height 0.4s var(--ease-paper);
  min-height: 1px;
}
.vd__hist-c {
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono);
  color: var(--blue);
  margin: 4px 0 2px;
  font-variant-numeric: tabular-nums;
}
.vd__hist-l {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink-mute);
  letter-spacing: 0.05em;
}

.vd__timing {
  list-style: none;
  margin: 0; padding: 0;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  border: 1px solid var(--rule);
}
.vd__timing li {
  padding: 10px 14px;
  border-right: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  background: var(--paper);
}
.vd__timing li:last-child { border-right: none; }
.vd__timing-l {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.05em;
}
.vd__timing-v {
  font-family: var(--mono);
  font-weight: 700;
  color: var(--blue);
  font-variant-numeric: tabular-nums;
}
.vd__timing-v small { color: var(--ink-mute); font-weight: 400; }

/* === 4. Drill-down === */
.vd__nav {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: var(--gap-4);
}
.vd__nav-no {
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono);
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}

.vd__qa {
  background: var(--paper);
  border: 1px solid var(--rule);
  padding: 18px 20px;
}
.vd__q { display: flex; gap: 14px; align-items: flex-start; }
.vd__q-seal {
  font-family: var(--serif);
  font-weight: 900;
  font-size: 18px;
  color: var(--blue);
  width: 32px; height: 32px;
  border: 2px solid var(--blue);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.vd__q-text {
  font-family: var(--serif);
  font-size: var(--fz-h4);
  font-weight: 600;
  color: var(--ink);
  margin: 0 0 8px;
  line-height: 1.6;
  text-indent: 0;
  font-style: italic;
}
.vd__q-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap-4);
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  align-items: center;
  letter-spacing: 0.05em;
}
.vd__q-meta b { color: var(--blue); font-weight: 700; }
.vd__q-meta code { background: var(--paper-deep); border: 1px solid var(--rule-fine); padding: 0 5px; font-size: 11px; }

.vd__hits-h {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-base);
  color: var(--ink);
  margin: var(--gap-4) 0 var(--gap-3);
  letter-spacing: 0.05em;
  border-bottom: 1px dashed var(--rule);
  padding-bottom: 4px;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}
.vd__hits-note {
  font-family: var(--mono);
  font-weight: 400;
  font-size: var(--fz-mono-sm);
  color: var(--blue);
  letter-spacing: 0.05em;
}
.vd__hits-note--miss {
  color: var(--red);
}
.vd__hits {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--gap-3);
}
.vd__hit {
  position: relative;
  border: 1px solid var(--rule);
  background: var(--paper-deep);
  display: flex;
  flex-direction: column;
}
.vd__hit--target { border: 2px solid var(--red); box-shadow: 0 0 0 1px var(--red); }
.vd__hit-rank {
  position: absolute;
  top: 4px; left: 4px;
  background: var(--blue);
  color: var(--paper);
  font-family: var(--mono);
  font-weight: 700;
  font-size: 10px;
  padding: 1px 6px;
  z-index: 2;
}
.vd__hit--target .vd__hit-rank { background: var(--red); }
.vd__hit img {
  width: 100%;
  height: 140px;
  object-fit: cover;
  object-position: top;
  display: block;
  background: var(--paper);
  filter: grayscale(0.1) sepia(0.04);
}
.vd__hit-meta {
  display: flex;
  justify-content: space-between;
  padding: 4px 8px;
  font-family: var(--mono);
  font-size: 10px;
  border-top: 1px solid var(--rule-fine);
}
.vd__hit-page { color: var(--ink); font-weight: 700; }
.vd__hit-score { color: var(--ink-mute); font-variant-numeric: tabular-nums; }
.vd__hit-tag {
  position: absolute;
  bottom: 32px; right: 4px;
  background: var(--red);
  color: var(--paper);
  font-family: var(--serif);
  font-weight: 700;
  font-size: 10px;
  padding: 2px 6px;
  letter-spacing: 0.1em;
}

.vd__foot {
  margin-top: var(--gap-7);
  padding: var(--gap-4) 0;
  border-top: 2px solid var(--ink);
  display: flex;
  justify-content: space-between;
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.18em;
}
.vd__foot-mono { font-variant-numeric: tabular-nums; }
</style>
