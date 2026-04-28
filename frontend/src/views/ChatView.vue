<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { chatApi, documentsApi, type ChatMessage, type RetrievalResult, type ChatSession, type DocumentInfo } from '../api/client'
import AnswerDisplay from '../components/AnswerDisplay.vue'
import PageViewer from '../components/PageViewer.vue'
import {
  AppPageHead, AppButton, AppTextarea, AppSelect, AppDialog, AppEmpty, msg,
} from '../design/primitives'
import Icon from '../design/Icons.vue'

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const loading = ref(false)
const currentSessionId = ref<string | undefined>(undefined)
const sessions = ref<ChatSession[]>([])
const allDocs = ref<DocumentInfo[]>([])
const scopedDocs = ref<string[]>([])
const topK = ref(5)
const threadRef = ref<HTMLDivElement | null>(null)
const viewerOpen = ref(false)
const viewerSource = ref<RetrievalResult | null>(null)

const viewerImageUrl = computed(() =>
  viewerSource.value
    ? `/api/images/${viewerSource.value.document_id}/page_${viewerSource.value.page_number}.png`
    : ''
)

const docOptions = computed(() => allDocs.value.map(d => ({ label: d.filename, value: d.id })))

const topKOptions = [
  { label: 'top · 3', value: 3 },
  { label: 'top · 5', value: 5 },
  { label: 'top · 10', value: 10 },
]

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text, sources: [], timestamp: new Date().toISOString() })
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
      timestamp: new Date().toISOString(),
    })
    await loadSessions()
  } catch {
    messages.value.pop()
    msg.error('发送失败')
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function scrollToBottom() {
  if (threadRef.value) threadRef.value.scrollTop = threadRef.value.scrollHeight
}

function newSession() {
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
  if (!confirm('确认删除此会话？')) return
  await chatApi.deleteSession(sessionId)
  if (currentSessionId.value === sessionId) {
    currentSessionId.value = undefined
    messages.value = []
  }
  msg.success('已删除')
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
  if (!first) return '（新建会话 · 暂无消息）'
  return first.content.slice(0, 30) + (first.content.length > 30 ? '⋯' : '')
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return `${(d.getMonth()+1).toString().padStart(2,'0')}.${d.getDate().toString().padStart(2,'0')} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
  } catch { return '' }
}

function shortDoc(id: string) {
  return id.length > 12 ? id.slice(0, 6) + '⋯' : id
}

function onThumbError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.cssText = 'opacity:.35;filter:grayscale(1)'
}

function openPageViewer(src: RetrievalResult) {
  viewerSource.value = src
  viewerOpen.value = true
}

function highlightSource(_msgIdx: number, srcIdx: number, src: RetrievalResult | undefined) {
  if (src) openPageViewer(src)
  void srcIdx
}

async function loadDocs() {
  try {
    const resp = await documentsApi.list()
    allDocs.value = resp.data.filter(d => d.status === 'completed')
  } catch {}
}

onMounted(async () => {
  await Promise.all([loadSessions(), loadDocs()])
})
</script>

<template>
  <div class="cv">
    <AppPageHead
      chapter="1"
      kicker="多轮对话"
      title="多轮对话"
      subtitle="在选定文档范围内进行多轮问答，系统检索相关页面并附引用来源"
      stamp="多轮&#10;对话"
    />

    <div class="cv__shell">
      <!-- 左侧：历史对话 -->
      <aside class="cv-side">
        <header class="cv-side__head">
          <span class="cv-side__l">会话列表</span>
          <AppButton variant="primary" size="sm" @click="newSession">
            <Icon name="plus" :size="13" />
            新建
          </AppButton>
        </header>
        <div class="cv-side__list">
          <button
            v-for="s in sessions"
            :key="s.session_id"
            type="button"
            class="cv-side-item"
            :class="{ 'cv-side-item--active': s.session_id === currentSessionId }"
            @click="loadSession(s.session_id)"
          >
            <div class="cv-side-item__no">№</div>
            <div class="cv-side-item__main">
              <div class="cv-side-item__preview">{{ sessionPreview(s) }}</div>
              <div class="cv-side-item__time">{{ formatTime(s.updated_at) }}</div>
            </div>
            <span
              class="cv-side-item__del"
              @click.stop="deleteSession(s.session_id)"
              title="删除"
            >
              <Icon name="close" :size="12" />
            </span>
          </button>
          <AppEmpty v-if="sessions.length === 0" text="暂无会话" hint='点击"新建"开始对话' />
        </div>
      </aside>

      <!-- 主对话区 -->
      <section class="cv-main">
        <!-- 工具栏 -->
        <div class="cv-tools">
          <div class="cv-tools__group">
            <span class="cv-tools__l">文档范围</span>
            <div class="cv-tools__field cv-tools__field--wide">
              <AppSelect
                :model-value="null"
                :options="docOptions"
                placeholder="可多选，留空则全部"
                size="sm"
                @change="(v) => v && !scopedDocs.includes(v as string) && scopedDocs.push(v as string)"
              />
            </div>
            <div class="cv-tools__chips" v-if="scopedDocs.length">
              <span v-for="(id, i) in scopedDocs" :key="id" class="cv-chip">
                <span class="cv-chip__txt">{{ allDocs.find(d => d.id === id)?.filename || shortDoc(id) }}</span>
                <button type="button" class="cv-chip__x" @click="scopedDocs.splice(i, 1)" aria-label="移除">
                  <Icon name="close" :size="10" />
                </button>
              </span>
            </div>
          </div>
          <div class="cv-tools__group">
            <span class="cv-tools__l">Top-K</span>
            <div class="cv-tools__field">
              <AppSelect v-model="topK" :options="topKOptions" size="sm" />
            </div>
          </div>
        </div>

        <!-- 对话流 -->
        <div ref="threadRef" class="cv-thread">
          <div v-if="messages.length === 0" class="cv-thread__empty">
            <div class="cv-thread__empty-mark">·</div>
            <p class="cv-thread__empty-zh">等待提问</p>
            <p class="cv-thread__empty-en">系统将检索文档并提供来源页码</p>
          </div>

          <article
            v-for="(m, i) in messages"
            :key="i"
            class="cv-msg"
            :class="`cv-msg--${m.role}`"
          >
            <div class="cv-msg__rail">
              <span class="cv-msg__seal">{{ m.role === 'user' ? '问' : '答' }}</span>
            </div>

            <div class="cv-msg__body">
              <template v-if="m.role === 'user'">
                <p class="cv-msg__q">{{ m.content }}</p>
              </template>
              <template v-else>
                <AnswerDisplay :answer="m.content" @cite="(idx) => highlightSource(i, idx, m.sources?.[idx])" />
                <div v-if="m.sources?.length" class="cv-cit">
                  <div class="cv-cit__head">
                    <span class="cv-cit__l">引用来源</span>
                    <span class="cv-cit__c">{{ m.sources.length }} 页</span>
                  </div>
                  <div class="cv-cit__row">
                    <button
                      v-for="(src, si) in m.sources"
                      :key="si"
                      type="button"
                      class="cv-thumb"
                      @click="openPageViewer(src)"
                    >
                      <span class="cv-thumb__cite">[{{ si + 1 }}]</span>
                      <img
                        :src="`/api/images/${src.document_id}/page_${src.page_number}.png`"
                        @error="onThumbError"
                        alt="page"
                      />
                      <span class="cv-thumb__pg">第 {{ src.page_number }} 页</span>
                    </button>
                  </div>
                </div>
              </template>
            </div>
          </article>

          <div v-if="loading" class="cv-msg cv-msg--assistant cv-msg--loading">
            <div class="cv-msg__rail"><span class="cv-msg__seal">答</span></div>
            <div class="cv-msg__body">
              <div class="cv-load">
                <span class="cv-load__d"></span>
                <span class="cv-load__d"></span>
                <span class="cv-load__d"></span>
                <span class="cv-load__t">检索中⋯</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="cv-input">
          <AppTextarea
            v-model="inputText"
            placeholder="输入问题，按 Ctrl + Enter 发送"
            :rows="2"
            @keydown.ctrl.enter.prevent="sendMessage"
          />
          <AppButton
            variant="primary"
            size="lg"
            :loading="loading"
            :disabled="!inputText.trim()"
            @click="sendMessage"
            class="cv-input__btn"
          >
            <Icon name="send" :size="14" />
            <span>发送</span>
          </AppButton>
        </div>
      </section>
    </div>

    <!-- 页面查看器 -->
    <AppDialog
      v-model="viewerOpen"
      :title="viewerSource ? `第 ${viewerSource.page_number} 页 · ${viewerSource.document_id.slice(0, 12)}` : ''"
      width="780px"
    >
      <PageViewer v-if="viewerSource" :image-url="viewerImageUrl" :layout="viewerSource.layout" />
    </AppDialog>
  </div>
</template>

<style scoped>
.cv {
  max-width: 1280px;
  margin: 0 auto;
  height: calc(100vh - var(--topbar-h) - var(--gap-7));
  display: flex;
  flex-direction: column;
}

.cv__shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  flex: 1;
  min-height: 0;
  gap: 0;
  border: 1px solid var(--rule);
  background: var(--paper);
}

/* Sidebar */
.cv-side {
  background: var(--paper-deep);
  border-right: 1px solid var(--rule);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.cv-side__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 2px solid var(--ink);
  background: var(--blue-deep);
  color: var(--paper);
}
.cv-side__l {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  letter-spacing: 0.2em;
  color: var(--paper);
}

.cv-side__list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.cv-side-item {
  width: 100%;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  padding: 10px 14px;
  background: transparent;
  border: none;
  border-bottom: 1px dotted var(--rule);
  text-align: left;
  cursor: pointer;
  position: relative;
  transition: background var(--dur-fast);
}
.cv-side-item:hover { background: var(--paper); }
.cv-side-item--active {
  background: var(--paper);
  border-left: 3px solid var(--red);
  padding-left: 11px;
}

.cv-side-item__no {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  font-weight: 700;
  color: var(--ink-mute);
  margin-top: 2px;
}
.cv-side-item__main { min-width: 0; }
.cv-side-item__preview {
  font-family: var(--serif);
  font-size: var(--fz-sm);
  color: var(--ink);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cv-side-item__time {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink-mute);
  letter-spacing: 0.1em;
  margin-top: 2px;
}
.cv-side-item__del {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px; height: 22px;
  color: var(--ink-mute);
  opacity: 0;
  transition: all var(--dur-fast);
  align-self: center;
}
.cv-side-item:hover .cv-side-item__del { opacity: 1; }
.cv-side-item__del:hover { color: var(--red); background: var(--red-tint); }

/* Main */
.cv-main {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.cv-tools {
  display: flex;
  gap: var(--gap-4);
  padding: 12px 18px;
  border-bottom: 1px solid var(--rule);
  background: var(--paper-deep);
  flex-wrap: wrap;
  align-items: center;
}
.cv-tools__group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.cv-tools__l {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--ink);
  letter-spacing: 0.2em;
}
.cv-tools__field { width: 140px; }
.cv-tools__field--wide { width: 220px; }

.cv-tools__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.cv-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--paper);
  border: 1px solid var(--blue);
  color: var(--blue);
  padding: 2px 6px 2px 8px;
  font-family: var(--serif);
  font-size: 12px;
  max-width: 180px;
}
.cv-chip__txt {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cv-chip__x {
  background: transparent;
  border: none;
  color: var(--blue);
  cursor: pointer;
  padding: 0;
  width: 14px; height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cv-chip__x:hover { color: var(--red); }

/* Thread */
.cv-thread {
  flex: 1;
  overflow-y: auto;
  padding: var(--gap-5) var(--gap-6);
  display: flex;
  flex-direction: column;
  gap: var(--gap-5);
}

.cv-thread__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--ink-mute);
}
.cv-thread__empty-mark {
  font-family: var(--serif);
  font-weight: 900;
  font-size: 80px;
  color: var(--red);
  line-height: 0.5;
  margin-bottom: 30px;
}
.cv-thread__empty-zh {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-h2);
  color: var(--ink);
  letter-spacing: 0.4em;
  margin: 0 0 8px;
}
.cv-thread__empty-en {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--ink-mute);
  letter-spacing: 0.18em;
  margin: 0;
}

/* Messages */
.cv-msg {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: var(--gap-4);
}

.cv-msg__rail {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 4px;
}
.cv-msg__seal {
  font-family: var(--serif);
  font-weight: 900;
  font-size: 18px;
  width: 36px; height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid currentColor;
  letter-spacing: 0;
}
.cv-msg--user .cv-msg__seal { color: var(--blue); }
.cv-msg--assistant .cv-msg__seal { color: var(--red); }

.cv-msg__body { min-width: 0; }
.cv-msg__q {
  font-family: var(--serif);
  font-size: var(--fz-h4);
  line-height: 1.7;
  color: var(--ink);
  border-left: 3px solid var(--blue);
  padding: 6px 18px;
  margin: 0;
  font-weight: 600;
  font-style: italic;
  background: var(--paper-deep);
  text-indent: 0;
}

/* Citations */
.cv-cit { margin-top: var(--gap-3); }
.cv-cit__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px dashed var(--rule);
  padding-bottom: 6px;
  margin-bottom: 10px;
}
.cv-cit__l {
  font-family: var(--serif);
  font-weight: 700;
  font-size: var(--fz-sm);
  color: var(--ink);
  letter-spacing: 0.2em;
}
.cv-cit__c {
  font-family: var(--mono);
  font-size: var(--fz-mono-sm);
  color: var(--red);
  letter-spacing: 0.1em;
  font-weight: 700;
}

.cv-cit__row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap-3);
}

.cv-thumb {
  position: relative;
  width: 110px;
  background: var(--paper);
  border: 1px solid var(--rule);
  cursor: pointer;
  padding: 0;
  display: flex;
  flex-direction: column;
  transition: all var(--dur-fast) var(--ease-paper);
}
.cv-thumb:hover {
  border-color: var(--red);
  transform: translateY(-2px);
  box-shadow: var(--shadow-2);
}

.cv-thumb__cite {
  position: absolute;
  top: 4px; left: 4px;
  background: var(--red);
  color: var(--paper);
  font-family: var(--mono);
  font-weight: 700;
  font-size: 10px;
  padding: 1px 6px;
  z-index: 2;
}
.cv-thumb img {
  width: 100%;
  height: 130px;
  object-fit: cover;
  object-position: top;
  display: block;
  background: var(--paper-deep);
  filter: grayscale(0.1) sepia(0.04);
}
.cv-thumb__pg {
  font-family: var(--serif);
  font-size: 11px;
  color: var(--ink);
  text-align: center;
  padding: 4px;
  border-top: 1px solid var(--rule);
  background: var(--paper-deep);
  letter-spacing: 0.1em;
}

/* Loading */
.cv-msg--loading .cv-load {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--paper-deep);
  border: 1px solid var(--rule);
  width: max-content;
}
.cv-load__d {
  width: 6px; height: 6px;
  background: var(--red);
  animation: cvload 1.2s infinite;
}
.cv-load__d:nth-child(2) { animation-delay: 0.15s; }
.cv-load__d:nth-child(3) { animation-delay: 0.3s; }
@keyframes cvload {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.7); }
  40% { opacity: 1; transform: scale(1.2); }
}
.cv-load__t {
  font-family: var(--serif);
  font-style: italic;
  font-size: var(--fz-sm);
  color: var(--ink-mute);
  margin-left: 8px;
  letter-spacing: 0.15em;
}

/* Input */
.cv-input {
  display: flex;
  gap: var(--gap-3);
  padding: 14px 18px;
  border-top: 2px solid var(--ink);
  background: var(--paper-deep);
  align-items: flex-end;
}
.cv-input :deep(.ta) { flex: 1; }
.cv-input__btn { flex-shrink: 0; }
</style>
