<template>
  <div v-if="results.length" class="evidence-panel">
    <div class="evidence-panel__header">
      <span class="evidence-panel__title">检索证据</span>
      <span class="evidence-panel__count">共 {{ results.length }} 页</span>
    </div>

    <div class="evidence-panel__grid">
      <div
        v-for="(r, i) in results"
        :key="i"
        class="evidence-card"
        :class="{ 'evidence-card--active': activeIndex === i }"
        @click="openViewer(i)"
      >
        <!-- Citation badge -->
        <div class="evidence-card__badge">[{{ i + 1 }}]</div>

        <!-- Thumbnail -->
        <div class="evidence-card__thumb">
          <img :src="imgUrl(r)" alt="page" loading="lazy" @error="onImgError" />
          <!-- element type mini-indicators -->
          <div v-if="r.layout?.elements.length" class="evidence-card__tags">
            <span
              v-for="type in uniqueTypes(r)"
              :key="type"
              class="evidence-card__tag"
              :style="{ background: typeColor(type) }"
            >{{ typeShort(type) }}</span>
          </div>
        </div>

        <!-- Meta -->
        <div class="evidence-card__meta">
          <div class="evidence-card__filename" :title="r.document_id">
            {{ shortId(r.document_id) }}
          </div>
          <div class="evidence-card__page">第 {{ r.page_number }} 页</div>
        </div>

        <!-- Score bar -->
        <div class="evidence-card__score-wrap">
          <div
            class="evidence-card__score-bar"
            :style="{ width: scorePercent(r.score) + '%' }"
          />
          <span class="evidence-card__score-val">{{ r.score.toFixed(4) }}</span>
        </div>
      </div>
    </div>

    <!-- Full-page viewer drawer -->
    <el-drawer
      v-model="drawerOpen"
      direction="rtl"
      size="50%"
      :title="`[${activeIndex + 1}] 第 ${activeResult?.page_number} 页`"
      destroy-on-close
    >
      <div v-if="activeResult" class="evidence-drawer">
        <PageViewer
          :image-url="imgUrl(activeResult)"
          :layout="activeResult.layout"
        />
        <!-- Layout element list -->
        <div v-if="activeResult.layout?.elements.length" class="evidence-drawer__elements">
          <div class="evidence-drawer__elements-title">版面元素 ({{ activeResult.layout.elements.length }})</div>
          <div
            v-for="(el, ei) in activeResult.layout.elements"
            :key="ei"
            class="evidence-drawer__element"
          >
            <span class="evidence-drawer__element-type" :style="{ background: typeColor(el.element_type) }">
              {{ typeLabel(el.element_type) }}
            </span>
            <span v-if="el.text" class="evidence-drawer__element-text">
              {{ el.text.slice(0, 100) }}{{ el.text.length > 100 ? '…' : '' }}
            </span>
            <span v-else-if="el.element_type === 'figure'" class="evidence-drawer__element-text">图片区域</span>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { RetrievalResult } from '../api/client'
import PageViewer from './PageViewer.vue'

const props = defineProps<{ results: RetrievalResult[] }>()
const emit = defineEmits<{ (e: 'cite', index: number): void }>()

const activeIndex = ref(-1)
const drawerOpen = ref(false)

const activeResult = computed(() =>
  activeIndex.value >= 0 ? props.results[activeIndex.value] : null
)

function openViewer(i: number) {
  activeIndex.value = i
  drawerOpen.value = true
  emit('cite', i)
}

function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.cssText = 'opacity:.35;filter:grayscale(1)'
  img.title = '图片文件不存在'
}

function imgUrl(r: RetrievalResult) {
  return `/api/images/${r.document_id}/page_${r.page_number}.png`
}

function shortId(id: string) {
  return id.length > 20 ? id.slice(0, 8) + '…' + id.slice(-6) : id
}

const maxScore = computed(() => Math.max(...props.results.map(r => r.score), 0.001))
function scorePercent(score: number) {
  return Math.round((score / maxScore.value) * 100)
}

const TYPE_COLORS: Record<string, string> = {
  text_block: 'rgba(96,165,250,0.25)',
  heading: 'rgba(251,146,60,0.25)',
  table: 'rgba(52,211,153,0.25)',
  figure: 'rgba(232,121,249,0.25)',
}
function typeColor(type: string) { return TYPE_COLORS[type] || 'rgba(148,163,184,0.25)' }

const TYPE_LABELS: Record<string, string> = {
  text_block: '文本', heading: '标题', table: '表格', figure: '图表',
}
function typeLabel(type: string) { return TYPE_LABELS[type] || type }
function typeShort(type: string) {
  const s: Record<string, string> = { text_block: '文', heading: '题', table: '表', figure: '图' }
  return s[type] || type[0]
}

function uniqueTypes(r: RetrievalResult): string[] {
  if (!r.layout?.elements.length) return []
  return [...new Set(r.layout.elements.map(e => e.element_type))]
}
</script>

<style scoped>
.evidence-panel { margin-top: 16px; }

.evidence-panel__header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 12px;
}
.evidence-panel__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text);
}
.evidence-panel__count {
  font-size: 12px;
  color: var(--color-text-muted);
}

.evidence-panel__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.evidence-card {
  background: var(--color-surface);
  border: 1.5px solid var(--color-border);
  border-radius: 10px;
  padding: 10px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
  position: relative;
}
.evidence-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
  transform: translateY(-2px);
}
.evidence-card--active {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(var(--color-primary-rgb), 0.2);
}

.evidence-card__badge {
  position: absolute;
  top: 8px;
  left: 8px;
  background: var(--color-primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 6px;
  z-index: 1;
  letter-spacing: 0.02em;
}

.evidence-card__thumb {
  position: relative;
  border-radius: 6px;
  overflow: hidden;
  background: var(--color-bg);
}
.evidence-card__thumb img {
  width: 100%;
  height: 140px;
  object-fit: contain;
  display: block;
}

.evidence-card__tags {
  position: absolute;
  bottom: 4px;
  right: 4px;
  display: flex;
  gap: 3px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.evidence-card__tag {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 600;
  color: var(--color-text);
}

.evidence-card__meta {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}
.evidence-card__filename {
  color: var(--color-text-muted);
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evidence-card__page {
  color: var(--color-text);
  font-weight: 600;
}

.evidence-card__score-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}
.evidence-card__score-bar {
  height: 4px;
  background: var(--color-primary);
  border-radius: 2px;
  flex: 1;
  max-width: calc(100% - 48px);
  opacity: 0.7;
}
.evidence-card__score-val {
  font-size: 10px;
  color: var(--color-text-muted);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

/* Drawer content */
.evidence-drawer { padding: 0 4px; }

.evidence-drawer__elements { margin-top: 16px; }
.evidence-drawer__elements-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}
.evidence-drawer__element {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 12px;
}
.evidence-drawer__element-type {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
  color: var(--color-text);
}
.evidence-drawer__element-text {
  color: var(--color-text-muted);
  line-height: 1.4;
}
</style>
