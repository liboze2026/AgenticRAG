<script setup lang="ts">
import { ref, computed } from 'vue'
import type { EvidenceRegion } from '../../api/client'

const props = defineProps<{
  imageUrl: string
  regions: EvidenceRegion[]
  pageWidth?: number
  pageHeight?: number
  activeCitation?: number
}>()

const emit = defineEmits<{ (e: 'pick', region: EvidenceRegion): void }>()

const imgSize = ref({ w: 0, h: 0 })

function onLoad(e: Event) {
  const img = e.target as HTMLImageElement
  imgSize.value = { w: img.naturalWidth, h: img.naturalHeight }
}

const useCoordSpace = computed(() => {
  // If pageWidth/pageHeight given, treat bbox coords as in that space.
  // Otherwise treat bbox as already pixel-space.
  if (props.pageWidth && props.pageHeight && props.pageWidth > 1 && props.pageHeight > 1) {
    return { w: props.pageWidth, h: props.pageHeight }
  }
  return null
})

function px(coord: number, axis: 'x' | 'y') {
  const space = useCoordSpace.value
  if (!space || imgSize.value.w === 0) return coord
  if (axis === 'x') return (coord / space.w) * imgSize.value.w
  return (coord / space.h) * imgSize.value.h
}

function isWholePage(r: EvidenceRegion): boolean {
  // Heuristic: bbox covers whole image (within 5%)
  const space = useCoordSpace.value
  const bw = r.bbox.x1 - r.bbox.x0
  const bh = r.bbox.y1 - r.bbox.y0
  if (!space) return bw <= 1.5 && bh <= 1.5
  return bw >= space.w * 0.95 && bh >= space.h * 0.95
}

const COLOR_BY_LABEL: Record<string, string> = {
  '正文': '#a83232',
  '标题': '#1a4480',
  '表格': '#7a3a8a',
  '图表': '#b86614',
}
function regionColor(r: EvidenceRegion): string {
  return COLOR_BY_LABEL[r.label] || '#a83232'
}

function isActive(r: EvidenceRegion): boolean {
  return props.activeCitation !== undefined && r.citation === props.activeCitation
}
</script>

<template>
  <div class="bo">
    <div class="bo__paper">
      <img :src="imageUrl" class="bo__img" @load="onLoad" alt="page" />
      <svg
        v-if="imgSize.w > 0"
        class="bo__svg"
        :viewBox="`0 0 ${imgSize.w} ${imgSize.h}`"
        xmlns="http://www.w3.org/2000/svg"
      >
        <g v-for="(r, i) in regions" :key="i">
          <template v-if="!isWholePage(r)">
            <rect
              :x="px(r.bbox.x0, 'x') - 2"
              :y="px(r.bbox.y0, 'y') - 2"
              :width="Math.max(4, px(r.bbox.x1, 'x') - px(r.bbox.x0, 'x') + 4)"
              :height="Math.max(4, px(r.bbox.y1, 'y') - px(r.bbox.y0, 'y') + 4)"
              :fill="regionColor(r) + (isActive(r) ? '22' : '11')"
              :stroke="regionColor(r)"
              :stroke-width="isActive(r) ? 5 : 3"
              :stroke-opacity="isActive(r) ? 1 : 0.85"
              class="bo__box"
              @click="emit('pick', r)"
            />
            <g v-if="r.citation > 0">
              <circle
                :cx="px(r.bbox.x0, 'x') + 14"
                :cy="px(r.bbox.y0, 'y') + 14"
                r="14"
                :fill="regionColor(r)"
              />
              <text
                :x="px(r.bbox.x0, 'x') + 14"
                :y="px(r.bbox.y0, 'y') + 19"
                text-anchor="middle"
                fill="#fff"
                font-family="JetBrains Mono, monospace"
                font-weight="800"
                font-size="14"
              >{{ r.citation }}</text>
            </g>
          </template>
          <template v-else>
            <rect
              x="6" y="6"
              :width="imgSize.w - 12"
              :height="imgSize.h - 12"
              fill="rgba(168, 50, 50, 0.04)"
              :stroke="regionColor(r)"
              stroke-width="3"
              stroke-dasharray="14 6"
              class="bo__box"
              @click="emit('pick', r)"
            />
            <g v-if="r.citation > 0">
              <rect :x="6" :y="6" width="60" height="28" :fill="regionColor(r)" />
              <text :x="36" :y="26" text-anchor="middle" fill="#fff"
                font-family="Noto Serif SC, serif" font-weight="700" font-size="14">[{{ r.citation }}]</text>
            </g>
          </template>
        </g>
      </svg>
    </div>
  </div>
</template>

<style scoped>
.bo { width: 100%; }
.bo__paper {
  position: relative;
  background: #fff;
  border: 1px solid var(--rule);
  box-shadow: var(--shadow-paper);
}
.bo__img { width: 100%; display: block; }
.bo__svg {
  position: absolute; top: 0; left: 0;
  width: 100%; height: 100%;
  pointer-events: none;
}
.bo__box {
  pointer-events: all;
  cursor: pointer;
  transition: stroke-width var(--dur-fast) var(--ease-paper);
}
.bo__box:hover { stroke-width: 6; }
</style>
