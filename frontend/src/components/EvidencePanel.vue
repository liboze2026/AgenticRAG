<script setup lang="ts">
import { ref, computed } from 'vue'
import type { RetrievalResult } from '../api/client'
import PageViewer from './PageViewer.vue'
import { AppDrawer, AppTag } from '../design/primitives'

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

function imgUrl(r: RetrievalResult) {
  return `/api/images/${r.document_id}/page_${r.page_number}.png`
}
function shortId(id: string) {
  return id.length > 20 ? id.slice(0, 8) + '⋯' + id.slice(-6) : id
}
function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.cssText = 'opacity:.35;filter:grayscale(1)'
}

const maxScore = computed(() => Math.max(...props.results.map(r => r.score), 0.001))
function scorePercent(score: number) {
  return Math.round((score / maxScore.value) * 100)
}

const TYPE_LABELS: Record<string, string> = {
  text_block: '正文', heading: '标题', table: '表格', figure: '图表',
}
function typeLabel(t: string) { return TYPE_LABELS[t] || t }
function uniqueTypes(r: RetrievalResult): string[] {
  if (!r.layout?.elements.length) return []
  return [...new Set(r.layout.elements.map(e => e.element_type))]
}
</script>

<template>
  <section v-if="results.length" class="ep">
    <div class="ep__head">
      <span class="ep__seal">源</span>
      <h3 class="ep__title">检索来源</h3>
      <span class="ep__count">共 <b>{{ results.length }}</b> 页</span>
    </div>

    <div class="ep__grid">
      <article
        v-for="(r, i) in results"
        :key="i"
        class="ep-card"
        :class="{ 'ep-card--active': activeIndex === i }"
        @click="openViewer(i)"
      >
        <div class="ep-card__cite">[{{ i + 1 }}]</div>

        <div class="ep-card__thumb">
          <img :src="imgUrl(r)" alt="page" loading="lazy" @error="onImgError" />
          <div class="ep-card__corner"></div>
        </div>

        <div class="ep-card__body">
          <div class="ep-card__row">
            <span class="ep-card__l">文档</span>
            <span class="ep-card__v" :title="r.document_id">{{ shortId(r.document_id) }}</span>
          </div>
          <div class="ep-card__row">
            <span class="ep-card__l">页码</span>
            <span class="ep-card__v ep-card__v--mono">第 {{ r.page_number }} 页</span>
          </div>
          <div class="ep-card__row">
            <span class="ep-card__l">得分</span>
            <span class="ep-card__v ep-card__v--mono">{{ r.score.toFixed(4) }}</span>
          </div>
        </div>

        <div class="ep-card__tags" v-if="uniqueTypes(r).length">
          <AppTag v-for="t in uniqueTypes(r)" :key="t" variant="paper" size="sm">{{ typeLabel(t) }}</AppTag>
        </div>

        <div class="ep-card__bar">
          <div class="ep-card__bar-fill" :style="{ width: scorePercent(r.score) + '%' }"></div>
        </div>
      </article>
    </div>

    <AppDrawer
      v-model="drawerOpen"
      :title="activeResult ? `[${activeIndex + 1}] 第 ${activeResult.page_number} 页 · ${shortId(activeResult.document_id)}` : ''"
      width="640px"
    >
      <div v-if="activeResult" class="ep-dr">
        <PageViewer :image-url="imgUrl(activeResult)" :layout="activeResult.layout" />

        <div v-if="activeResult.layout?.elements.length" class="ep-dr__elements">
          <div class="ep-dr__title">
            <span>版面元素</span>
            <span class="ep-dr__count">{{ activeResult.layout.elements.length }} 项</span>
          </div>
          <ol class="ep-dr__list">
            <li v-for="(el, ei) in activeResult.layout.elements" :key="ei" class="ep-dr__item">
              <span class="ep-dr__no">{{ String(ei + 1).padStart(2, '0') }}</span>
              <AppTag :variant="'paper'" size="sm">{{ typeLabel(el.element_type) }}</AppTag>
              <span class="ep-dr__text">
                <template v-if="el.text">{{ el.text.slice(0, 140) }}{{ el.text.length > 140 ? '⋯' : '' }}</template>
                <template v-else-if="el.element_type === 'figure'">（图像区域）</template>
              </span>
            </li>
          </ol>
        </div>
      </div>
    </AppDrawer>
  </section>
</template>

<style scoped>
.ep { margin-top: var(--gap-5); }

.ep__head {
  display: flex;
  align-items: center;
  gap: var(--gap-3);
  margin-bottom: var(--gap-4);
  border-bottom: 1px solid var(--rule);
  padding-bottom: 8px;
}
.ep__seal {
  font-family: var(--serif);
  font-weight: 900;
  font-size: 18px;
  color: var(--red);
  width: 32px; height: 32px;
  border: 2px solid var(--red);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.ep__title {
  flex: 1;
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h3);
  color: var(--blue);
  margin: 0;
  letter-spacing: 0.18em;
}
.ep__count {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.1em;
}
.ep__count b { color: var(--red); font-weight: 700; font-variant-numeric: tabular-nums; margin: 0 2px; }

.ep__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--gap-4);
}

.ep-card {
  position: relative;
  background: var(--paper);
  border: 1px solid var(--rule);
  cursor: pointer;
  transition: transform var(--dur-fast) var(--ease-paper),
              box-shadow var(--dur-fast) var(--ease-paper),
              border-color var(--dur-fast) var(--ease-paper);
  display: flex;
  flex-direction: column;
}
.ep-card:hover {
  transform: translateY(-3px);
  border-color: var(--ink);
  box-shadow: var(--shadow-3);
}
.ep-card--active {
  border-color: var(--red);
  border-width: 2px;
}

.ep-card__cite {
  position: absolute;
  top: 6px; left: 6px;
  background: var(--red);
  color: var(--paper);
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono-sm);
  padding: 2px 8px;
  letter-spacing: 0.05em;
  z-index: 2;
}

.ep-card__thumb {
  position: relative;
  height: 160px;
  background: var(--paper-deep);
  border-bottom: 1px solid var(--rule);
  overflow: hidden;
}
.ep-card__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top;
  filter: grayscale(0.1) sepia(0.04);
}
.ep-card__corner {
  position: absolute;
  top: 0; right: 0;
  width: 24px; height: 24px;
  background: var(--paper);
  border-left: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
}

.ep-card__body {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}
.ep-card__row {
  display: flex;
  justify-content: space-between;
  font-size: var(--fz-mono-sm);
  border-bottom: 1px dotted var(--rule-fine);
  padding: 3px 0;
}
.ep-card__l {
  font-family: var(--serif);
  color: var(--ink-mute);
  letter-spacing: 0.15em;
  font-size: 11px;
}
.ep-card__v {
  color: var(--ink);
  font-weight: 600;
  font-family: var(--serif);
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
  max-width: 110px;
}
.ep-card__v--mono { font-family: var(--mono); font-variant-numeric: tabular-nums; color: var(--blue); }

.ep-card__tags {
  padding: 0 12px 8px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.ep-card__bar {
  height: 3px;
  background: var(--paper-deep);
}
.ep-card__bar-fill {
  height: 100%;
  background: var(--red);
  transition: width var(--dur-base) var(--ease-paper);
}

/* Drawer detail */
.ep-dr {
  display: flex;
  flex-direction: column;
  gap: var(--gap-5);
}
.ep-dr__title {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h4);
  color: var(--ink);
  letter-spacing: 0.18em;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 6px;
  margin-bottom: 10px;
}
.ep-dr__count {
  font-family: var(--mono);
  font-weight: 400;
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.1em;
}

.ep-dr__list { list-style: none; margin: 0; padding: 0; }
.ep-dr__item {
  display: grid;
  grid-template-columns: 30px auto 1fr;
  gap: 10px;
  align-items: baseline;
  padding: 8px 0;
  border-bottom: 1px dotted var(--rule);
}
.ep-dr__no {
  font-family: var(--mono);
  font-weight: 700;
  font-size: var(--fz-mono-sm);
  color: var(--red);
}
.ep-dr__text {
  color: var(--ink-soft);
  font-family: var(--serif);
  font-size: var(--fz-sm);
  line-height: 1.6;
}
</style>
