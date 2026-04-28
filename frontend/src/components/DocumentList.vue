<script setup lang="ts">
import type { DocumentInfo } from '../api/client'
import { AppEmpty, AppButton, AppTag } from '../design/primitives'

defineProps<{ documents: DocumentInfo[] }>()
defineEmits<{ (e: 'delete', id: string): void; (e: 'retry', id: string): void }>()

function progress(doc: DocumentInfo) {
  if (doc.total_pages === 0) return 0
  return Math.round((doc.indexed_pages / doc.total_pages) * 100)
}

function shortId(id: string) {
  return id.length > 12 ? id.slice(0, 6) + '⋯' + id.slice(-4) : id
}

function statusLabel(s: string) {
  return ({ completed: '已 编 目', indexing: '编 目 中', pending: '待 处 理', failed: '处 理 失 败' } as Record<string,string>)[s] || s
}

function statusVar(s: string): 'ok' | 'warn' | 'red' | 'mute' {
  return ({ completed: 'ok', indexing: 'warn', pending: 'mute', failed: 'red' } as const)[s as 'completed'] || 'mute'
}
</script>

<template>
  <AppEmpty v-if="documents.length === 0" text="尚无藏目" hint="upload pdf to begin" />
  <div v-else class="dl">
    <article
      v-for="doc in documents"
      :key="doc.id"
      class="dl-card"
      :class="`dl-card--${doc.status}`"
    >
      <header class="dl-card__head">
        <span class="dl-card__no">№ {{ shortId(doc.id) }}</span>
        <AppTag :variant="statusVar(doc.status)" size="sm">{{ statusLabel(doc.status) }}</AppTag>
      </header>

      <div class="dl-card__cover">
        <img
          :src="`/api/images/${doc.id}/page_1.png`"
          :alt="doc.filename"
          loading="lazy"
          @error="(e) => ((e.target as HTMLImageElement).style.display = 'none')"
        />
        <div class="dl-card__cover-fold"></div>
      </div>

      <div class="dl-card__body">
        <h4 class="dl-card__name" :title="doc.filename">{{ doc.filename }}</h4>
        <dl class="dl-card__meta">
          <div class="dl-card__row">
            <dt>页　数</dt>
            <dd>{{ doc.total_pages }}</dd>
          </div>
          <div class="dl-card__row">
            <dt>已索引</dt>
            <dd>{{ doc.indexed_pages }} / {{ doc.total_pages }}</dd>
          </div>
          <div class="dl-card__row" v-if="doc.dataset_id">
            <dt>所属集</dt>
            <dd># {{ doc.dataset_id }}</dd>
          </div>
        </dl>

        <div v-if="doc.status === 'indexing' || doc.status === 'completed'" class="dl-card__bar">
          <div class="dl-card__bar-track">
            <div class="dl-card__bar-fill" :style="{ width: progress(doc) + '%' }"></div>
          </div>
          <span class="dl-card__bar-pct">{{ progress(doc) }}<small>%</small></span>
        </div>
      </div>

      <footer class="dl-card__foot">
        <AppButton v-if="doc.status === 'failed'" variant="ghost" size="sm" @click="$emit('retry', doc.id)">
          重 试
        </AppButton>
        <AppButton variant="red" size="sm" @click="$emit('delete', doc.id)">
          注 销
        </AppButton>
      </footer>
    </article>
  </div>
</template>

<style scoped>
.dl {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--gap-5);
}

.dl-card {
  background: var(--paper);
  border: 1px solid var(--rule);
  display: flex;
  flex-direction: column;
  position: relative;
  transition: transform var(--dur-fast) var(--ease-paper),
              box-shadow var(--dur-fast) var(--ease-paper),
              border-color var(--dur-fast) var(--ease-paper);
  box-shadow: var(--shadow-2);
}
.dl-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-3);
  border-color: var(--ink);
}
.dl-card--failed { border-left: 3px solid var(--red); }
.dl-card--completed { border-left: 3px solid var(--ok); }
.dl-card--indexing { border-left: 3px solid var(--warn); }
.dl-card--pending { border-left: 3px solid var(--rule); }

.dl-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px dotted var(--rule);
  background: var(--paper-deep);
}
.dl-card__no {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  font-weight: 700;
  color: var(--ink-mute);
  letter-spacing: 0.1em;
}

.dl-card__cover {
  position: relative;
  height: 180px;
  background: var(--paper-deep);
  border-bottom: 1px solid var(--rule);
  overflow: hidden;
}
.dl-card__cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top;
  filter: grayscale(0.15) sepia(0.05);
}
.dl-card__cover-fold {
  position: absolute;
  top: 0; right: 0;
  width: 28px; height: 28px;
  background: var(--paper);
  border-left: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  box-shadow: -2px 2px 6px -2px rgba(0,0,0,.2);
}

.dl-card__body {
  padding: 14px 14px 10px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--gap-3);
}
.dl-card__name {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--ink);
  margin: 0;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  min-height: 2.8em;
}

.dl-card__meta {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.dl-card__row {
  display: flex;
  justify-content: space-between;
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  border-bottom: 1px dotted var(--rule-fine);
  padding: 2px 0;
}
.dl-card__row dt {
  color: var(--ink-mute);
  letter-spacing: 0.15em;
  font-family: var(--serif);
  font-size: 11px;
}
.dl-card__row dd {
  color: var(--ink);
  margin: 0;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.dl-card__bar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dl-card__bar-track {
  flex: 1;
  height: 4px;
  background: var(--paper-deep);
  border: 1px solid var(--rule);
}
.dl-card__bar-fill {
  height: 100%;
  background: var(--blue);
  transition: width var(--dur-base) var(--ease-paper);
}
.dl-card__bar-pct {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  font-weight: 700;
  color: var(--blue);
  font-variant-numeric: tabular-nums;
}
.dl-card__bar-pct small {
  color: var(--ink-mute);
  font-weight: 400;
  font-size: 10px;
  margin-left: 1px;
}

.dl-card__foot {
  padding: 8px 12px;
  border-top: 1px dashed var(--rule);
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  background: var(--paper-deep);
}
</style>
