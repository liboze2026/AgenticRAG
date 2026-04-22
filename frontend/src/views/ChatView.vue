<template>
  <div class="chat-view">
    <!-- Sidebar: sessions -->
    <div class="chat-sidebar">
      <div class="chat-sidebar__header">
        <span class="chat-sidebar__title">对话记录</span>
        <el-button type="primary" size="small" @click="newSession">新建</el-button>
      </div>
      <div class="chat-sidebar__list">
        <div
          v-for="s in sessions"
          :key="s.session_id"
          class="chat-sidebar__item"
          :class="{ 'chat-sidebar__item--active': s.session_id === currentSessionId }"
          @click="loadSession(s.session_id)"
        >
          <div class="chat-sidebar__item-preview">
            {{ sessionPreview(s) }}
          </div>
          <div class="chat-sidebar__item-time">{{ formatTime(s.updated_at) }}</div>
          <el-button
            size="small"
            text
            type="danger"
            class="chat-sidebar__del"
            @click.stop="deleteSession(s.session_id)"
          >×</el-button>
        </div>
        <div v-if="sessions.length === 0" class="chat-sidebar__empty">暂无对话</div>
      </div>
    </div>

    <!-- Main chat area -->
    <div class="chat-main">
      <div class="chat-view__title">智能对话</div>
      <!-- Toolbar -->
      <div class="chat-toolbar">
        <el-select
          v-model="scopedDocs"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="文档范围（空=全部）"
          size="small"
          style="min-width: 260px"
          clearable
        >
          <el-option
            v-for="doc in allDocs"
            :key="doc.id"
            :label="doc.filename"
            :value="doc.id"
          />
        </el-select>
        <el-select v-model="topK" size="small" style="width: 100px">
          <el-option :value="3" label="Top-3" />
          <el-option :value="5" label="Top-5" />
          <el-option :value="10" label="Top-10" />
        </el-select>
      </div>

      <!-- Message thread -->
      <div class="chat-thread" ref="threadRef">
        <div v-if="messages.length === 0" class="chat-thread__empty">
          <div class="chat-thread__hint">💬 开始提问，系统将自动检索相关文档页面并生成回答</div>
        </div>

        <div
          v-for="(msg, i) in messages"
          :key="i"
          class="chat-bubble-row"
          :class="msg.role === 'user' ? 'chat-bubble-row--user' : 'chat-bubble-row--assistant'"
        >
          <div class="chat-bubble" :class="`chat-bubble--${msg.role}`">
            <!-- User message -->
            <template v-if="msg.role === 'user'">
              <div class="chat-bubble__text">{{ msg.content }}</div>
            </template>

            <!-- Assistant message -->
            <template v-else>
              <AnswerDisplay :answer="msg.content" @cite="(idx) => highlightSource(i, idx)" />
              <!-- Source thumbnails inline -->
              <div v-if="msg.sources?.length" class="chat-bubble__sources">
                <div class="chat-bubble__sources-label">引用页面</div>
                <div class="chat-bubble__sources-row">
                  <div
                    v-for="(src, si) in msg.sources"
                    :key="si"
                    class="chat-source-thumb"
                    :class="{ 'chat-source-thumb--active': highlightedSource === `${i}-${si}` }"
                    @click="openPageViewer(src, si)"
                  >
                    <div class="chat-source-thumb__badge">[{{ si + 1 }}]</div>
                    <img :src="`/api/images/${src.document_id}/page_${src.page_number}.png`" alt="" />
                    <div class="chat-source-thumb__page">第{{ src.page_number }}页</div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- Loading bubble -->
        <div v-if="loading" class="chat-bubble-row chat-bubble-row--assistant">
          <div class="chat-bubble chat-bubble--assistant chat-bubble--loading">
            <span class="chat-loading-dot" />
            <span class="chat-loading-dot" />
            <span class="chat-loading-dot" />
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="chat-input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          :autosize="{ minRows: 1, maxRows: 5 }"
          placeholder="输入问题，按 Ctrl+Enter 发送…"
          @keydown.ctrl.enter.prevent="sendMessage"
          :disabled="loading"
          class="chat-input"
          resize="none"
        />
        <el-button
          type="primary"
          :loading="loading"
          @click="sendMessage"
          :disabled="!inputText.trim()"
          class="chat-send-btn"
        >发送</el-button>
      </div>
    </div>

    <!-- Page viewer dialog -->
    <el-dialog v-model="viewerOpen" width="60%" destroy-on-close title="页面详情">
      <PageViewer v-if="viewerSource" :image-url="viewerImageUrl" :layout="viewerSource.layout" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { chatApi, documentsApi, type ChatMessage, type RetrievalResult, type ChatSession, type DocumentInfo } from '../api/client'
import AnswerDisplay from '../components/AnswerDisplay.vue'
import PageViewer from '../components/PageViewer.vue'

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const loading = ref(false)
const currentSessionId = ref<string | undefined>(undefined)
const sessions = ref<ChatSession[]>([])
const allDocs = ref<DocumentInfo[]>([])
const scopedDocs = ref<string[]>([])
const topK = ref(5)
const threadRef = ref<HTMLDivElement>()
const highlightedSource = ref('')
const viewerOpen = ref(false)
const viewerSource = ref<RetrievalResult | null>(null)

const viewerImageUrl = computed(() =>
  viewerSource.value
    ? `/api/images/${viewerSource.value.document_id}/page_${viewerSource.value.page_number}.png`
    : ''
)

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  // Optimistic: show user bubble immediately
  messages.value.push({ role: 'user', content: text, sources: [], timestamp: '' })
  inputText.value = ''
  loading.value = true
  await nextTick()
  scrollToBottom()

  try {
    const apiMessages = messages.value
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .map(m => ({ role: m.role, content: m.content }))

    const resp = await chatApi.send(apiMessages, scopedDocs.value, currentSessionId.value, topK.value)
    currentSessionId.value = resp.data.session_id

    messages.value.push({
      role: 'assistant',
      content: resp.data.message.content,
      sources: resp.data.sources,
      timestamp: '',
    })
    await loadSessions()
  } catch {
    messages.value.pop() // remove optimistic user bubble on error
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function scrollToBottom() {
  if (threadRef.value) threadRef.value.scrollTop = threadRef.value.scrollHeight
}

async function newSession() {
  currentSessionId.value = undefined
  messages.value = []
  scopedDocs.value = []
}

async function loadSession(sessionId: string) {
  try {
    const resp = await chatApi.getSession(sessionId)
    currentSessionId.value = sessionId
    messages.value = resp.data.messages
    scopedDocs.value = resp.data.document_ids
    await nextTick()
    scrollToBottom()
  } catch {}
}

async function deleteSession(sessionId: string) {
  await chatApi.deleteSession(sessionId)
  if (currentSessionId.value === sessionId) {
    currentSessionId.value = undefined
    messages.value = []
  }
  await loadSessions()
}

async function loadSessions() {
  try {
    const resp = await chatApi.listSessions()
    sessions.value = resp.data
  } catch {}
}

function sessionPreview(s: ChatSession): string {
  const first = s.messages.find(m => m.role === 'user')
  if (!first) return '（新对话）'
  return first.content.slice(0, 40) + (first.content.length > 40 ? '…' : '')
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

function highlightSource(msgIdx: number, srcIdx: number) {
  highlightedSource.value = `${msgIdx}-${srcIdx}`
}

function openPageViewer(src: RetrievalResult, _idx: number) {
  viewerSource.value = src
  viewerOpen.value = true
}

onMounted(async () => {
  await Promise.all([loadSessions(), loadDocs()])
})

async function loadDocs() {
  try {
    const resp = await documentsApi.list()
    allDocs.value = resp.data.filter(d => d.status === 'completed')
  } catch {}
}
</script>

<style scoped>
.chat-view {
  display: flex;
  height: calc(100vh - 60px);
  gap: 0;
  overflow: hidden;
}

/* Sidebar */
.chat-sidebar {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
}
.chat-sidebar__header {
  padding: 14px 12px 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--color-border);
}
.chat-sidebar__title {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text);
}
.chat-sidebar__list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}
.chat-sidebar__item {
  padding: 10px 12px;
  cursor: pointer;
  border-radius: 6px;
  margin: 0 6px 2px;
  position: relative;
  transition: background 0.15s;
}
.chat-sidebar__item:hover { background: var(--color-bg); }
.chat-sidebar__item--active { background: rgba(var(--color-primary-rgb), 0.1); }
.chat-sidebar__item-preview {
  font-size: 12px;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 20px;
}
.chat-sidebar__item-time {
  font-size: 10px;
  color: var(--color-text-muted);
  margin-top: 2px;
}
.chat-sidebar__del {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0;
  transition: opacity 0.15s;
  padding: 0 4px !important;
}
.chat-sidebar__item:hover .chat-sidebar__del { opacity: 1; }
.chat-sidebar__empty {
  padding: 24px;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-muted);
}

/* Main area */
.chat-view__title { font-size: 16px; font-weight: 700; color: var(--text-primary); padding: 12px 20px 0; flex-shrink: 0; }
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.chat-toolbar {
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  gap: 10px;
  align-items: center;
  background: var(--color-surface);
}
.chat-thread {
  flex: 1;
  overflow-y: auto;
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.chat-thread__empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.chat-thread__hint {
  color: var(--color-text-muted);
  font-size: 14px;
  text-align: center;
  padding: 40px;
}

/* Bubbles */
.chat-bubble-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.chat-bubble-row--user { justify-content: flex-end; }
.chat-bubble-row--assistant { justify-content: flex-start; }

.chat-bubble {
  max-width: 75%;
  border-radius: 12px;
  padding: 10px 14px;
  position: relative;
}
.chat-bubble--user {
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.chat-bubble--assistant {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-bottom-left-radius: 4px;
}
.chat-bubble__text {
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: inherit;
}

/* Loading dots */
.chat-bubble--loading {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 14px 18px;
}
.chat-loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-muted);
  animation: bounce 1.2s infinite;
}
.chat-loading-dot:nth-child(2) { animation-delay: 0.2s; }
.chat-loading-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

/* Source thumbnails */
.chat-bubble__sources { margin-top: 10px; }
.chat-bubble__sources-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}
.chat-bubble__sources-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.chat-source-thumb {
  position: relative;
  width: 72px;
  cursor: pointer;
  border: 1.5px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
  transition: border-color 0.15s, transform 0.15s;
}
.chat-source-thumb:hover {
  border-color: var(--color-primary);
  transform: scale(1.04);
}
.chat-source-thumb--active { border-color: var(--color-primary); }
.chat-source-thumb__badge {
  position: absolute;
  top: 3px;
  left: 3px;
  background: var(--color-primary);
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 4px;
  z-index: 1;
}
.chat-source-thumb img {
  width: 100%;
  height: 54px;
  object-fit: contain;
  display: block;
  background: var(--color-bg);
}
.chat-source-thumb__page {
  font-size: 9px;
  text-align: center;
  color: var(--color-text-muted);
  padding: 2px 0;
  background: var(--color-surface);
}

/* Input */
.chat-input-area {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  display: flex;
  gap: 10px;
  align-items: flex-end;
  background: var(--color-surface);
}
.chat-input { flex: 1; }
.chat-send-btn { flex-shrink: 0; height: 40px; }
</style>
