<template>
  <div v-if="documents.length === 0" class="doc-list__empty">
    <el-empty description="暂无文档，请上传 PDF" />
  </div>
  <div v-else class="doc-list__grid">
    <div
      v-for="doc in documents"
      :key="doc.id"
      class="doc-card"
      :class="`doc-card--${doc.status}`"
    >
      <!-- Thumbnail -->
      <div class="doc-card__thumb">
        <img
          :src="`/api/images/${doc.id}/page_1.png`"
          alt="封面"
          loading="lazy"
          @error="(e) => ((e.target as HTMLImageElement).style.display = 'none')"
        />
        <div class="doc-card__status-dot" :class="`dot--${doc.status}`" :title="doc.status" />
      </div>

      <!-- Body -->
      <div class="doc-card__body">
        <div class="doc-card__name" :title="doc.filename">{{ doc.filename }}</div>

        <div class="doc-card__meta">
          <span>{{ doc.total_pages }} 页</span>
          <el-tag
            v-if="doc.dataset_id"
            size="small"
            type="info"
            class="doc-card__dataset"
          >#{{ doc.dataset_id }}</el-tag>
        </div>

        <!-- Progress bar for indexing -->
        <el-progress
          v-if="doc.status === 'indexing' || doc.status === 'completed'"
          :percentage="progress(doc)"
          :status="doc.status === 'completed' ? 'success' : undefined"
          :stroke-width="4"
          :show-text="false"
          class="doc-card__progress"
        />
        <div v-if="doc.status === 'indexing'" class="doc-card__progress-text">
          {{ doc.indexed_pages }} / {{ doc.total_pages }} 页已索引
        </div>
        <el-tag v-if="doc.status === 'failed'" type="danger" size="small">索引失败</el-tag>
        <el-tag v-if="doc.status === 'pending'" type="info" size="small">等待中</el-tag>
      </div>

      <!-- Actions -->
      <div class="doc-card__actions">
        <el-button
          v-if="doc.status === 'failed'"
          type="warning"
          size="small"
          text
          @click="$emit('retry', doc.id)"
        >重试</el-button>
        <el-button
          type="danger"
          size="small"
          text
          @click="$emit('delete', doc.id)"
        >删除</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DocumentInfo } from '../api/client'

defineProps<{ documents: DocumentInfo[] }>()
defineEmits<{ (e: 'delete', id: string): void; (e: 'retry', id: string): void }>()

function progress(doc: DocumentInfo) {
  if (doc.total_pages === 0) return 0
  return Math.round((doc.indexed_pages / doc.total_pages) * 100)
}
</script>

<style scoped>
.doc-list__empty { padding: 40px 0; }

.doc-list__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}

.doc-card {
  background: var(--color-surface);
  border: 1.5px solid var(--color-border);
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.2s, transform 0.15s;
}
.doc-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
  transform: translateY(-1px);
}
.doc-card--failed { border-color: rgba(239,68,68,0.4); }
.doc-card--completed { border-color: rgba(52,211,153,0.3); }

.doc-card__thumb {
  position: relative;
  height: 120px;
  background: var(--color-bg);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.doc-card__thumb img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.doc-card__status-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--color-surface);
}
.dot--completed { background: #34d399; }
.dot--indexing { background: #fbbf24; animation: pulse 1.5s infinite; }
.dot--failed { background: #ef4444; }
.dot--pending { background: #94a3b8; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.doc-card__body {
  padding: 10px 12px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.doc-card__name {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc-card__meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--color-text-muted);
}
.doc-card__progress { margin-top: 2px; }
.doc-card__progress-text {
  font-size: 10px;
  color: var(--color-text-muted);
}

.doc-card__actions {
  padding: 6px 8px;
  border-top: 1px solid var(--color-border);
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}
</style>
