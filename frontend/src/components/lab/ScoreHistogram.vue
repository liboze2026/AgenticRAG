<script setup lang="ts">
import { computed } from 'vue'
import type { ScoreBucket, GmmComponent } from '../../api/client'

const props = defineProps<{
  histogram: ScoreBucket[]
  components: GmmComponent[]    // 0: low cluster, 1: high cluster
  cutoffScore: number
}>()

const W = 720
const H = 240
const PAD_L = 48
const PAD_R = 16
const PAD_T = 18
const PAD_B = 36

const innerW = W - PAD_L - PAD_R
const innerH = H - PAD_T - PAD_B

const xRange = computed(() => {
  if (!props.histogram.length) return { lo: 0, hi: 1 }
  const lo = props.histogram[0].bin_start
  const hi = props.histogram[props.histogram.length - 1].bin_end
  return { lo, hi: hi > lo ? hi : lo + 1 }
})

const maxCount = computed(() => Math.max(1, ...props.histogram.map(b => b.count)))

function xScale(s: number): number {
  const { lo, hi } = xRange.value
  if (hi - lo < 1e-9) return PAD_L
  return PAD_L + ((s - lo) / (hi - lo)) * innerW
}

function gaussian(x: number, mean: number, variance: number): number {
  if (variance <= 0) return 0
  const sd = Math.sqrt(variance)
  return Math.exp(-0.5 * Math.pow((x - mean) / sd, 2)) / (sd * Math.sqrt(2 * Math.PI))
}

const SAMPLES = 80

interface CurvePoint { x: number; y: number }
function buildCurve(c: GmmComponent): CurvePoint[] {
  const { lo, hi } = xRange.value
  const out: CurvePoint[] = []
  // Find peak density to scale to chart height
  let peak = 0
  for (let i = 0; i <= SAMPLES; i++) {
    const s = lo + (i / SAMPLES) * (hi - lo)
    const d = gaussian(s, c.mean, c.variance) * c.weight
    if (d > peak) peak = d
  }
  if (peak <= 0) return out
  for (let i = 0; i <= SAMPLES; i++) {
    const s = lo + (i / SAMPLES) * (hi - lo)
    const d = gaussian(s, c.mean, c.variance) * c.weight
    out.push({ x: xScale(s), y: PAD_T + innerH - (d / peak) * innerH * 0.85 })
  }
  return out
}

const lowCurve = computed(() => props.components[0] ? buildCurve(props.components[0]) : [])
const highCurve = computed(() => props.components[1] ? buildCurve(props.components[1]) : [])

function pathFromPoints(pts: CurvePoint[]): string {
  if (!pts.length) return ''
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
}

function ticks(): number[] {
  const { lo, hi } = xRange.value
  const out: number[] = []
  for (let i = 0; i <= 4; i++) out.push(lo + (i / 4) * (hi - lo))
  return out
}
</script>

<template>
  <div class="sh">
    <svg :viewBox="`0 0 ${W} ${H}`" class="sh__svg" xmlns="http://www.w3.org/2000/svg">
      <!-- Grid -->
      <line v-for="t in ticks()" :key="`g-${t}`"
        :x1="xScale(t)" :x2="xScale(t)"
        :y1="PAD_T" :y2="PAD_T + innerH"
        stroke="#ddd" stroke-dasharray="2 4" />
      <!-- Histogram bars -->
      <g>
        <rect
          v-for="(b, i) in histogram" :key="`b-${i}`"
          :x="xScale(b.bin_start) + 1"
          :y="PAD_T + innerH - (b.count / maxCount) * innerH"
          :width="Math.max(1, xScale(b.bin_end) - xScale(b.bin_start) - 2)"
          :height="(b.count / maxCount) * innerH"
          fill="#c7d4e8"
          stroke="#1a4480"
          stroke-width="1"
        />
      </g>
      <!-- Cutoff line -->
      <line v-if="cutoffScore > 0"
        :x1="xScale(cutoffScore)" :x2="xScale(cutoffScore)"
        :y1="PAD_T" :y2="PAD_T + innerH"
        stroke="#a83232" stroke-width="2" stroke-dasharray="6 3" />
      <text v-if="cutoffScore > 0"
        :x="xScale(cutoffScore)" :y="PAD_T - 4"
        fill="#a83232"
        font-family="JetBrains Mono, monospace" font-weight="700" font-size="11"
        text-anchor="middle">截断 {{ cutoffScore.toFixed(3) }}</text>
      <!-- GMM curves -->
      <path :d="pathFromPoints(lowCurve)"
        fill="none" stroke="#999" stroke-width="2" stroke-dasharray="4 2" />
      <path :d="pathFromPoints(highCurve)"
        fill="none" stroke="#a83232" stroke-width="2.5" />
      <!-- Axis -->
      <line :x1="PAD_L" :x2="W - PAD_R" :y1="PAD_T + innerH" :y2="PAD_T + innerH" stroke="#333" stroke-width="1" />
      <line :x1="PAD_L" :x2="PAD_L" :y1="PAD_T" :y2="PAD_T + innerH" stroke="#333" stroke-width="1" />
      <text v-for="t in ticks()" :key="`t-${t}`"
        :x="xScale(t)" :y="PAD_T + innerH + 16"
        text-anchor="middle"
        font-family="JetBrains Mono, monospace" font-size="10" fill="#666">
        {{ t.toFixed(2) }}
      </text>
      <text :x="W - PAD_R" :y="H - 6" text-anchor="end"
        font-family="Noto Serif SC, serif" font-size="10" fill="#999"
        letter-spacing="0.15em">分数</text>
    </svg>
    <div class="sh__legend">
      <span class="sh__l-tag" data-c="hist">候选分布</span>
      <span class="sh__l-tag" data-c="low">低峰 (噪声簇)</span>
      <span class="sh__l-tag" data-c="high">高峰 (相关簇)</span>
      <span class="sh__l-tag" data-c="cut">动态截断</span>
    </div>
  </div>
</template>

<style scoped>
.sh { width: 100%; }
.sh__svg { width: 100%; height: auto; max-height: 280px; }
.sh__legend {
  display: flex; flex-wrap: wrap; gap: 12px;
  margin-top: 8px;
  padding: 6px 12px;
  background: var(--paper-deep); border: 1px solid var(--rule);
  font-family: var(--mono); font-size: 10px;
  color: var(--ink-soft); letter-spacing: 0.05em;
}
.sh__l-tag::before {
  content: ''; display: inline-block;
  width: 14px; height: 6px; margin-right: 4px;
  vertical-align: middle;
}
.sh__l-tag[data-c="hist"]::before { background: #c7d4e8; border: 1px solid #1a4480; }
.sh__l-tag[data-c="low"]::before { background: transparent; border-top: 2px dashed #999; height: 2px; }
.sh__l-tag[data-c="high"]::before { background: #a83232; height: 3px; }
.sh__l-tag[data-c="cut"]::before { background: transparent; border-top: 2px dashed #a83232; height: 2px; }
</style>
