<script setup lang="ts">
import { ref, computed } from 'vue'
import type { PageLayout, LayoutElement } from '../api/client'

const props = defineProps<{
  imageUrl: string
  layout?: PageLayout | null
  showTypes?: string[]
}>()

const imgSize = ref({ w: 0, h: 0 })
const hoverIndex = ref(-1)

function onImageLoad(e: Event) {
  const img = e.target as HTMLImageElement
  imgSize.value = { w: img.naturalWidth, h: img.naturalHeight }
}

function toPixel(coord: number, axis: 'x' | 'y'): number {
  if (!props.layout) return 0
  if (axis === 'x') return (coord / props.layout.page_width) * imgSize.value.w
  return (coord / props.layout.page_height) * imgSize.value.h
}

const visibleElements = computed<LayoutElement[]>(() => {
  if (!props.layout) return []
  const els = props.layout.elements
  if (!props.showTypes || props.showTypes.length === 0) return els
  return els.filter(e => props.showTypes!.includes(e.element_type))
})

const TYPE_LABELS: Record<string, string> = {
  text_block: '正文', heading: '标题', table: '表格', figure: '图表',
}
function elementLabel(type: string): string { return TYPE_LABELS[type] || type }

const uniqueTypes = computed(() => [...new Set(visibleElements.value.map(e => e.element_type))])
</script>

<template>
  <div class="pv">
    <div class="pv__paper">
      <img :src="imageUrl" class="pv__img" @load="onImageLoad" alt="文档页面" />
      <svg
        v-if="layout && imgSize.w > 0"
        class="pv__overlay"
        :viewBox="`0 0 ${imgSize.w} ${imgSize.h}`"
        xmlns="http://www.w3.org/2000/svg"
      >
        <g v-for="(el, i) in visibleElements" :key="i">
          <!-- 双重 stroke 模拟毛笔朱批 -->
          <rect
            :x="toPixel(el.bbox.x0, 'x') - 2"
            :y="toPixel(el.bbox.y0, 'y') - 2"
            :width="toPixel(el.bbox.x1, 'x') - toPixel(el.bbox.x0, 'x') + 4"
            :height="toPixel(el.bbox.y1, 'y') - toPixel(el.bbox.y0, 'y') + 4"
            fill="rgba(168, 50, 50, 0.06)"
            stroke="rgba(168, 50, 50, 0.85)"
            :stroke-width="hoverIndex === i ? 4 : 2.5"
            class="pv__bbox"
            @mouseenter="hoverIndex = i"
            @mouseleave="hoverIndex = -1"
          />
          <text
            :x="toPixel(el.bbox.x0, 'x')"
            :y="toPixel(el.bbox.y0, 'y') - 6"
            font-family="Noto Serif SC, serif"
            font-weight="700"
            font-size="14"
            fill="#a83232"
            class="pv__lbl"
          >{{ String(i + 1).padStart(2, '0') }} · {{ elementLabel(el.element_type) }}</text>
        </g>
      </svg>
    </div>

    <div v-if="uniqueTypes.length" class="pv__legend">
      <span class="pv__legend-l">图例</span>
      <span v-for="t in uniqueTypes" :key="t" class="pv__legend-tag">
        <span class="pv__legend-dot"></span>{{ elementLabel(t) }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.pv { width: 100%; }

.pv__paper {
  position: relative;
  display: block;
  width: 100%;
  background: #fff;
  border: 1px solid var(--rule);
  box-shadow: var(--shadow-paper);
}

.pv__img {
  width: 100%;
  display: block;
}

.pv__overlay {
  position: absolute;
  top: 0; left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.pv__bbox {
  pointer-events: all;
  cursor: default;
  transition: stroke-width var(--dur-fast) var(--ease-paper);
}
.pv__lbl {
  pointer-events: none;
  paint-order: stroke;
  stroke: var(--paper);
  stroke-width: 2.5px;
  letter-spacing: 0.05em;
}

.pv__legend {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--gap-3);
  margin-top: var(--gap-3);
  padding: 8px 12px;
  background: var(--paper-deep);
  border: 1px solid var(--rule);
  font-size: var(--fz-mono-sm);
  font-family: var(--mono);
}
.pv__legend-l {
  font-family: var(--serif);
  font-weight: 700;
  color: var(--ink);
  letter-spacing: 0.15em;
  margin-right: 4px;
  font-size: var(--fz-sm);
}
.pv__legend-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-soft);
  text-transform: uppercase;
  letter-spacing: var(--ls-medium);
}
.pv__legend-dot {
  width: 9px; height: 9px;
  background: var(--red);
  display: inline-block;
}
</style>
