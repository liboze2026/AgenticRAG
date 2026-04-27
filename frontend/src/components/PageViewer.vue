<template>
  <div class="page-viewer">
    <div class="page-viewer__image-wrap" ref="wrapRef">
      <img
        :src="imageUrl"
        class="page-viewer__img"
        @load="onImageLoad"
        alt="Document page"
      />
      <!-- SVG overlay for bounding boxes -->
      <svg
        v-if="layout && imgSize.w > 0"
        class="page-viewer__overlay"
        :viewBox="`0 0 ${imgSize.w} ${imgSize.h}`"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect
          v-for="(el, i) in visibleElements"
          :key="i"
          :x="toPixel(el.bbox.x0, 'x')"
          :y="toPixel(el.bbox.y0, 'y')"
          :width="toPixel(el.bbox.x1, 'x') - toPixel(el.bbox.x0, 'x')"
          :height="toPixel(el.bbox.y1, 'y') - toPixel(el.bbox.y0, 'y')"
          :fill="elementColor(el.element_type, 0.12)"
          :stroke="elementColor(el.element_type, 0.8)"
          stroke-width="1.5"
          rx="2"
          class="page-viewer__bbox"
          @mouseenter="hoverIndex = i"
          @mouseleave="hoverIndex = -1"
        />
        <!-- Label for hovered element -->
        <text
          v-if="hoverIndex >= 0"
          :x="toPixel(visibleElements[hoverIndex].bbox.x0, 'x') + 4"
          :y="toPixel(visibleElements[hoverIndex].bbox.y0, 'y') + 14"
          font-size="11"
          :fill="elementColor(visibleElements[hoverIndex].element_type, 1)"
          font-weight="600"
        >{{ elementLabel(visibleElements[hoverIndex].element_type) }}</text>
      </svg>
    </div>

    <!-- Element type legend -->
    <div v-if="layout && layout.elements.length" class="page-viewer__legend">
      <span
        v-for="type in uniqueTypes"
        :key="type"
        class="page-viewer__legend-item"
        :style="{ borderColor: elementColor(type, 0.8), color: elementColor(type, 1) }"
      >{{ elementLabel(type) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { PageLayout, LayoutElement } from '../api/client'

const props = defineProps<{
  imageUrl: string
  layout?: PageLayout | null
  showTypes?: string[]   // filter which element types to render; empty = all
}>()

const wrapRef = ref<HTMLDivElement>()
const imgSize = ref({ w: 0, h: 0 })
const hoverIndex = ref(-1)

function onImageLoad(e: Event) {
  const img = e.target as HTMLImageElement
  imgSize.value = { w: img.naturalWidth, h: img.naturalHeight }
}

// pdfplumber uses top-left origin (top/bottom), same direction as pixels
// We just scale from PDF points → pixels using the image natural size
function toPixel(coord: number, axis: 'x' | 'y'): number {
  if (!props.layout) return 0
  if (axis === 'x') {
    return (coord / props.layout.page_width) * imgSize.value.w
  }
  return (coord / props.layout.page_height) * imgSize.value.h
}

const visibleElements = computed<LayoutElement[]>(() => {
  if (!props.layout) return []
  const els = props.layout.elements
  if (!props.showTypes || props.showTypes.length === 0) return els
  return els.filter(e => props.showTypes!.includes(e.element_type))
})

const uniqueTypes = computed(() =>
  [...new Set(visibleElements.value.map(e => e.element_type))]
)

const TYPE_COLORS: Record<string, string> = {
  text_block: '96,165,250',  // blue-400
  heading: '251,146,60',     // orange-400
  table: '52,211,153',       // emerald-400
  figure: '232,121,249',     // fuchsia-400
}

function elementColor(type: string, alpha: number): string {
  const rgb = TYPE_COLORS[type] || '148,163,184'
  return `rgba(${rgb},${alpha})`
}

function elementLabel(type: string): string {
  const labels: Record<string, string> = {
    text_block: '文本块',
    heading: '标题',
    table: '表格',
    figure: '图表',
  }
  return labels[type] || type
}
</script>

<style scoped>
.page-viewer {
  width: 100%;
}

.page-viewer__image-wrap {
  position: relative;
  display: inline-block;
  width: 100%;
}

.page-viewer__img {
  width: 100%;
  display: block;
  border-radius: 6px;
}

.page-viewer__overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.page-viewer__bbox {
  pointer-events: all;
  cursor: default;
  transition: fill 0.15s;
}

.page-viewer__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.page-viewer__legend-item {
  font-size: 11px;
  padding: 2px 8px;
  border: 1.5px solid;
  border-radius: 10px;
  background: rgba(255,255,255,0.05);
}
</style>
