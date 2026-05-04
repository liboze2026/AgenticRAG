<script setup lang="ts">
import type { ChannelResult, RetrievalResult } from '../../api/client'

defineProps<{
  channel: ChannelResult
  title: string
  variant?: 'sparse' | 'dense' | 'fused'
}>()

function imgUrl(r: RetrievalResult) {
  return `/api/images/${r.document_id}/page_${r.page_number}.png`
}
function shortId(id: string) {
  return id.length > 12 ? id.slice(0, 6) + '⋯' + id.slice(-3) : id
}
function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.cssText = 'opacity:.3;filter:grayscale(1)'
}
</script>

<template>
  <div class="cc" :data-variant="variant ?? 'dense'">
    <header class="cc__head">
      <span class="cc__seal">{{ title.slice(0, 1) }}</span>
      <div class="cc__title-wrap">
        <h4 class="cc__title">{{ title }}</h4>
        <span class="cc__sub">{{ channel.channel.toUpperCase() }} · {{ channel.timing_ms.toFixed(0) }} ms</span>
      </div>
      <span class="cc__count">{{ channel.results.length }}</span>
    </header>
    <div v-if="channel.note" class="cc__note">{{ channel.note }}</div>

    <div v-if="!channel.results.length" class="cc__empty">无命中</div>
    <ol v-else class="cc__list">
      <li v-for="(r, i) in channel.results" :key="`${r.document_id}-${r.page_number}-${i}`" class="cc__item">
        <span class="cc__rank">{{ String(i + 1).padStart(2, '0') }}</span>
        <div class="cc__thumb">
          <img :src="imgUrl(r)" loading="lazy" alt="page" @error="onImgError" />
        </div>
        <div class="cc__meta">
          <div class="cc__row">
            <span class="cc__l">页</span>
            <span class="cc__v">{{ r.page_number }}</span>
          </div>
          <div class="cc__row">
            <span class="cc__l">分</span>
            <span class="cc__v cc__v--mono">{{ r.score.toFixed(3) }}</span>
          </div>
          <div class="cc__row" :title="r.document_id">
            <span class="cc__l">文档</span>
            <span class="cc__v cc__v--mono">{{ shortId(r.document_id) }}</span>
          </div>
        </div>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.cc {
  background: var(--paper);
  border: 1px solid var(--rule);
  border-top: 3px solid var(--ink);
  display: flex;
  flex-direction: column;
  min-height: 120px;
}
.cc[data-variant="sparse"] { border-top-color: var(--blue); }
.cc[data-variant="dense"]  { border-top-color: var(--red); }
.cc[data-variant="fused"]  { border-top-color: var(--ink); background: var(--paper-deep); }

.cc__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--rule);
}
.cc__seal {
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--serif); font-weight: 900;
  background: var(--ink); color: var(--paper);
  flex-shrink: 0;
  font-size: 14px;
}
.cc[data-variant="sparse"] .cc__seal { background: var(--blue); }
.cc[data-variant="dense"]  .cc__seal { background: var(--red); }
.cc__title-wrap { flex: 1; min-width: 0; }
.cc__title {
  margin: 0;
  font-family: var(--serif); font-weight: 700;
  font-size: var(--fz-h4); color: var(--ink);
  letter-spacing: 0.15em;
}
.cc__sub {
  font-family: var(--mono); font-size: 10px;
  color: var(--ink-mute); letter-spacing: 0.1em;
}
.cc__count {
  font-family: var(--mono); font-weight: 700;
  font-size: 18px; color: var(--ink-mute);
  font-variant-numeric: tabular-nums;
}
.cc__note {
  padding: 6px 12px;
  background: var(--paper-deep);
  font-size: var(--fz-mono-sm); font-family: var(--mono);
  color: var(--ink-soft);
  border-bottom: 1px dotted var(--rule);
}
.cc__empty {
  padding: 28px; text-align: center;
  font-family: var(--serif); color: var(--ink-mute);
  font-size: var(--fz-sm); letter-spacing: 0.1em;
}
.cc__list { list-style: none; margin: 0; padding: 0; }
.cc__item {
  display: grid;
  grid-template-columns: 30px 70px 1fr;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px dotted var(--rule);
  align-items: center;
}
.cc__item:hover { background: var(--paper-deep); }
.cc__rank {
  font-family: var(--mono); font-weight: 700;
  font-size: 14px; color: var(--red);
  text-align: center;
}
.cc__thumb {
  height: 48px;
  background: var(--paper-deep);
  border: 1px solid var(--rule);
  overflow: hidden;
}
.cc__thumb img {
  width: 100%; height: 100%;
  object-fit: cover; object-position: top;
}
.cc__meta { display: flex; flex-direction: column; gap: 2px; }
.cc__row { display: flex; gap: 6px; font-size: var(--fz-mono-sm); }
.cc__l {
  font-family: var(--serif);
  color: var(--ink-mute);
  font-size: 10px;
  letter-spacing: 0.15em;
  width: 28px;
}
.cc__v {
  color: var(--ink); font-weight: 600;
  font-family: var(--serif);
}
.cc__v--mono {
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  color: var(--blue);
}
</style>
