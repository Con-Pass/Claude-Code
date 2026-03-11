<template>
  <!-- フローティングボタン（完全に閉じた状態） -->
  <button v-if="!open" class="chat-fab" @click="openPanel" title="AIアシスタント">
    <span class="fab-icon">✦</span>
    <span class="fab-label">AI アシスタント</span>
  </button>

  <!-- 最小化バー -->
  <Transition name="chat-mini">
    <div v-if="open && minimized" class="chat-mini-bar" @click="minimized = false">
      <div class="chat-mini-left">
        <div class="chat-avatar chat-avatar-sm">✦</div>
        <div>
          <div class="chat-title" style="font-size:13px;">ConPass AI</div>
          <div class="chat-subtitle">{{ currentSession ? currentSession.title : '新しい会話' }}</div>
        </div>
      </div>
      <div class="chat-mini-actions">
        <button class="chat-header-btn" @click.stop="minimized = false" title="展開">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="18 15 12 9 6 15"/>
          </svg>
        </button>
        <button class="chat-header-btn" @click.stop="open = false; minimized = false" title="閉じる">✕</button>
      </div>
    </div>
  </Transition>

  <!-- チャットパネル -->
  <Transition name="chat-slide">
    <div v-if="open && !minimized" class="chat-panel">

      <!-- ヘッダー -->
      <div class="chat-header">
        <div class="chat-header-left">
          <div class="chat-avatar">✦</div>
          <div>
            <div class="chat-title">ConPass AI</div>
            <div class="chat-subtitle">
              {{ currentSession ? currentSession.title : '新しい会話' }}
            </div>
          </div>
        </div>
        <div class="chat-header-actions">
          <button class="chat-header-btn" @click="minimized = true" title="最小化">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
          <button class="chat-header-btn" @click="open = false" title="閉じる">✕</button>
        </div>
      </div>

      <!-- ボディ（サイドバー＋メイン） -->
      <div class="chat-body">

        <!-- ===== サイドバー ===== -->
        <aside class="chat-sidebar">
          <button class="new-chat-btn" @click="newChat">
            <span class="new-chat-icon">＋</span>新しい会話
          </button>

          <div class="sidebar-section-label" v-if="sessions.length > 0">履歴</div>

          <div class="sidebar-list">
            <div
              v-for="s in sessions"
              :key="s.id"
              class="sidebar-item"
              :class="{ active: s.id === currentSessionId }"
              @click="selectSession(s)"
              :title="s.title"
            >
              <div class="sidebar-item-body">
                <div class="sidebar-item-title">{{ s.title }}</div>
                <div class="sidebar-item-date">{{ formatRelativeTime(s.updatedAt) }}</div>
              </div>
              <button
                class="sidebar-item-delete"
                @click.stop="deleteSession(s.id)"
                title="削除"
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>
                  <path d="M10 11v6M14 11v6" stroke="currentColor" stroke-width="2" fill="none"/>
                </svg>
              </button>
            </div>
          </div>

          <div v-if="sessions.length === 0" class="sidebar-empty">
            まだ会話がありません
          </div>
        </aside>

        <!-- ===== メインエリア ===== -->
        <div class="chat-main">
          <!-- メッセージ一覧 -->
          <div class="chat-messages" ref="messagesEl">

            <!-- ウェルカム（新規会話のみ） -->
            <div v-if="messages.length === 0" class="welcome-area">
              <div class="welcome-icon">✦</div>
              <div class="welcome-title">ConPass AI へようこそ</div>
              <div class="welcome-desc">
                契約書の内容や条項について何でも聞いてください。<br>
                アップロードしたファイルを元に回答します。
              </div>
              <div class="suggestion-list">
                <button
                  v-for="s in suggestions"
                  :key="s"
                  class="suggestion-btn"
                  @click="sendSuggestion(s)"
                >{{ s }}</button>
              </div>
            </div>

            <!-- メッセージバブル -->
            <div
              v-for="msg in messages"
              :key="msg.id"
              class="msg-row"
              :class="msg.role === 'user' ? 'msg-row-user' : 'msg-row-assistant'"
            >
              <div v-if="msg.role === 'assistant'" class="msg-avatar-sm">✦</div>
              <div
                class="msg-bubble"
                :class="msg.role === 'user' ? 'bubble-user' : 'bubble-assistant'"
              >
                <div class="msg-text" v-html="renderText(msg.content)"></div>
                <div class="msg-time">{{ formatTime(msg.time) }}</div>
              </div>
            </div>

            <!-- 待機中 -->
            <div v-if="loading" class="msg-row msg-row-assistant">
              <div class="msg-avatar-sm">✦</div>
              <div class="msg-bubble bubble-assistant">
                <div class="typing-dots">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>

          <!-- エラー -->
          <div v-if="errorMsg" class="chat-error">
            <span>{{ errorMsg }}</span>
            <button @click="errorMsg = ''">✕</button>
          </div>

          <!-- 入力エリア -->
          <div class="chat-input-area">
            <textarea
              ref="inputEl"
              class="chat-input"
              v-model="inputText"
              placeholder="メッセージを入力..."
              rows="1"
              maxlength="2000"
              @keydown.enter.exact="handleEnter"
              @keydown.shift.enter="() => {}"
              @input="autoResize"
            ></textarea>
            <button
              class="send-btn"
              :disabled="!inputText.trim() || loading"
              @click="sendMessage"
              title="送信"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2 21l21-9L2 3v7l15 2-15 2z"/>
              </svg>
            </button>
          </div>
          <div class="chat-footer">
            Enter で送信 · Shift+Enter で改行
            <span
              v-if="inputText.length > 1800"
              :style="{ color: inputText.length >= 2000 ? '#e53e3e' : '#a0aec0', marginLeft: '8px' }"
            >{{ inputText.length }}/2000</span>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'

// ===== 型定義 =====
interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  time: Date
}

interface StoredMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  time: string  // ISO string
}

interface ChatSession {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: StoredMessage[]
}

// ===== 定数 =====
const STORAGE_KEY = 'conpass-ai-chat-sessions'
const MAX_SESSIONS = 50

const suggestions = [
  '契約書の主な条項を教えて',
  '解約条件について説明して',
  '有効期限に関する記述はある？',
  '自動更新の条項を探して',
]

// ===== refs =====
const open           = ref(false)
const minimized      = ref(false)
const inputText      = ref('')
const loading        = ref(false)
const errorMsg       = ref('')
const messagesEl     = ref<HTMLElement | null>(null)
const inputEl        = ref<HTMLTextAreaElement | null>(null)

const sessions          = ref<ChatSession[]>([])
const currentSessionId  = ref<string | null>(null)
const messages          = ref<Message[]>([])

let nextId = 1

// ===== computed =====
const currentSession = computed(() =>
  sessions.value.find(s => s.id === currentSessionId.value) ?? null
)

// ===== localStorage =====
function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) sessions.value = JSON.parse(raw)
  } catch { sessions.value = [] }
}

function saveSessions() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.value))
  } catch { /* quota exceeded など */ }
}

// ===== セッション管理 =====
function openPanel() {
  open.value = true
  if (sessions.value.length > 0 && !currentSessionId.value) {
    // 最新の会話を自動選択
    selectSession(sessions.value[0])
  }
}

function newChat() {
  currentSessionId.value = null
  messages.value = []
  errorMsg.value = ''
  nextTick(() => inputEl.value?.focus())
}

function selectSession(session: ChatSession) {
  currentSessionId.value = session.id
  messages.value = session.messages.map(m => ({
    ...m,
    time: new Date(m.time),
  }))
  errorMsg.value = ''
  nextTick(scrollToBottom)
}

function deleteSession(sessionId: string) {
  sessions.value = sessions.value.filter(s => s.id !== sessionId)
  saveSessions()
  if (currentSessionId.value === sessionId) {
    newChat()
  }
}

function getOrCreateSession(firstMessage: string): string {
  if (currentSessionId.value) return currentSessionId.value

  const newSession: ChatSession = {
    id: crypto.randomUUID(),
    title: firstMessage.slice(0, 40) + (firstMessage.length > 40 ? '…' : ''),
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    messages: [],
  }
  sessions.value = [newSession, ...sessions.value].slice(0, MAX_SESSIONS)
  currentSessionId.value = newSession.id
  saveSessions()
  return newSession.id
}

function persistMessages() {
  const sid = currentSessionId.value
  if (!sid) return
  const idx = sessions.value.findIndex(s => s.id === sid)
  if (idx === -1) return
  sessions.value[idx] = {
    ...sessions.value[idx],
    updatedAt: new Date().toISOString(),
    messages: messages.value.map(m => ({
      ...m,
      time: m.time.toISOString(),
    })),
  }
  // 最新を先頭に
  const updated = sessions.value.splice(idx, 1)[0]
  sessions.value.unshift(updated)
  saveSessions()
}

// ===== チャット =====
function handleEnter(e: KeyboardEvent) {
  if (e.isComposing) return
  e.preventDefault()
  sendMessage()
}

async function sendSuggestion(text: string) {
  inputText.value = text
  await sendMessage()
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  errorMsg.value = ''
  getOrCreateSession(text)

  messages.value.push({ id: nextId++, role: 'user', content: text, time: new Date() })
  inputText.value = ''
  if (inputEl.value) inputEl.value.style.height = 'auto'
  persistMessages()
  await scrollToBottom()

  loading.value = true
  try {
    const apiMessages = messages.value.map(m => ({ role: m.role, content: m.content }))
    const response = await fetch('/agent-api/api/v1/chat/non-streaming', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Frontend-Env': 'local' },
      credentials: 'include',
      body: JSON.stringify({
        messages: apiMessages,
        data: { type: 'general' },
      }),
    })
    if (!response.ok) {
      const errText = await response.text()
      throw new Error(`HTTP ${response.status}: ${errText.slice(0, 120)}`)
    }
    const json = await response.json()
    const answer = json?.result?.content ?? json?.content ?? JSON.stringify(json)
    messages.value.push({ id: nextId++, role: 'assistant', content: answer, time: new Date() })
  } catch (e: any) {
    errorMsg.value = e?.message ?? 'AIエージェントサービスに接続できません'
  } finally {
    loading.value = false
    persistMessages()
    await scrollToBottom()
  }
}

// ===== UI ユーティリティ =====
function autoResize() {
  if (!inputEl.value) return
  inputEl.value.style.height = 'auto'
  inputEl.value.style.height = Math.min(inputEl.value.scrollHeight, 120) + 'px'
}

async function scrollToBottom() {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

function formatTime(d: Date) {
  return d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
}

function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime()
  const min  = Math.floor(diff / 60_000)
  const hr   = Math.floor(diff / 3_600_000)
  const day  = Math.floor(diff / 86_400_000)
  if (min  <  1) return 'たった今'
  if (min  < 60) return `${min}分前`
  if (hr   < 24) return `${hr}時間前`
  if (day  <  7) return `${day}日前`
  return new Date(isoString).toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' })
}

function renderText(text: string): string {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/### (.*?)(\n|$)/g, '<h4>$1</h4>')
    .replace(/## (.*?)(\n|$)/g, '<h3>$1</h3>')
    .replace(/\n/g, '<br>')
}

onMounted(loadSessions)
</script>

<style scoped>
/* ===== フローティングボタン ===== */
.chat-fab {
  position: fixed;
  bottom: 28px;
  right: 28px;
  z-index: 1000;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border: none;
  border-radius: 50px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(99,102,241,0.45);
  transition: transform 0.15s, box-shadow 0.15s;
}
.chat-fab:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(99,102,241,0.55);
}
.fab-icon { font-size: 16px; }

/* ===== ヘッダーボタン群 ===== */
.chat-header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.chat-header-btn {
  background: none;
  border: none;
  color: #a0aec0;
  font-size: 15px;
  cursor: pointer;
  padding: 5px 7px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
  line-height: 1;
}
.chat-header-btn:hover { background: rgba(255,255,255,0.1); color: #fff; }

/* ===== 最小化バー ===== */
.chat-mini-bar {
  position: fixed;
  bottom: 0;
  right: 28px;
  width: 280px;
  z-index: 1001;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #1e1e2e;
  color: #fff;
  border-radius: 12px 12px 0 0;
  box-shadow: 0 -4px 20px rgba(0,0,0,0.25);
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}
.chat-mini-bar:hover { background: #2a2a3e; }
.chat-mini-left { display: flex; align-items: center; gap: 10px; }
.chat-avatar-sm { width: 26px; height: 26px; font-size: 11px; flex-shrink: 0; }
.chat-mini-actions { display: flex; align-items: center; gap: 2px; }

/* 最小化アニメーション */
.chat-mini-enter-active,
.chat-mini-leave-active {
  transition: transform 0.2s cubic-bezier(0.4,0,0.2,1), opacity 0.2s;
}
.chat-mini-enter-from,
.chat-mini-leave-to {
  transform: translateY(100%);
  opacity: 0;
}

/* ===== パネル全体 ===== */
.chat-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 55vw;
  min-width: 640px;
  max-width: 900px;
  z-index: 1001;
  display: flex;
  flex-direction: column;
  background: #fff;
  box-shadow: -4px 0 32px rgba(0,0,0,0.18);
}

/* スライドアニメーション */
.chat-slide-enter-active,
.chat-slide-leave-active {
  transition: transform 0.25s cubic-bezier(0.4,0,0.2,1), opacity 0.25s;
}
.chat-slide-enter-from,
.chat-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

/* ===== ヘッダー ===== */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: #1e1e2e;
  color: #fff;
  flex-shrink: 0;
  z-index: 1;
}
.chat-header-left { display: flex; align-items: center; gap: 12px; }
.chat-avatar {
  width: 34px;
  height: 34px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
}
.chat-title   { font-size: 14px; font-weight: 700; }
.chat-subtitle {
  font-size: 11px;
  color: #a0aec0;
  margin-top: 1px;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ===== ボディ（横並び） ===== */
.chat-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ===== サイドバー ===== */
.chat-sidebar {
  width: 200px;
  flex-shrink: 0;
  background: #13131f;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid #2a2a3e;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: calc(100% - 24px);
  margin: 12px;
  padding: 9px 12px;
  background: rgba(99,102,241,0.15);
  border: 1px solid rgba(99,102,241,0.35);
  border-radius: 8px;
  color: #a5b4fc;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  flex-shrink: 0;
}
.new-chat-btn:hover {
  background: rgba(99,102,241,0.25);
  border-color: rgba(99,102,241,0.6);
  color: #c4b5fd;
}
.new-chat-icon { font-size: 16px; line-height: 1; }

.sidebar-section-label {
  padding: 4px 14px 6px;
  font-size: 10px;
  font-weight: 700;
  color: #4a4a6a;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  flex-shrink: 0;
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 12px;
}
.sidebar-list::-webkit-scrollbar { width: 4px; }
.sidebar-list::-webkit-scrollbar-thumb { background: #2a2a3e; border-radius: 2px; }

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s;
  position: relative;
}
.sidebar-item:hover { background: rgba(255,255,255,0.06); }
.sidebar-item.active { background: rgba(99,102,241,0.18); }

.sidebar-item-body { flex: 1; min-width: 0; }
.sidebar-item-title {
  font-size: 12px;
  color: #c8c8e0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}
.sidebar-item.active .sidebar-item-title { color: #e0e0ff; }
.sidebar-item-date {
  font-size: 10px;
  color: #4a4a6a;
  margin-top: 2px;
}

.sidebar-item-delete {
  display: none;
  background: none;
  border: none;
  color: #6060a0;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  flex-shrink: 0;
  transition: color 0.12s, background 0.12s;
}
.sidebar-item-delete:hover { color: #e53e3e; background: rgba(229,62,62,0.12); }
.sidebar-item:hover .sidebar-item-delete { display: flex; align-items: center; }

.sidebar-empty {
  padding: 24px 12px;
  font-size: 11px;
  color: #4a4a6a;
  text-align: center;
  line-height: 1.6;
}

/* ===== メインエリア ===== */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
}

/* ===== メッセージ ===== */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: #fafafa;
}

.welcome-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 24px;
  text-align: center;
}
.welcome-icon {
  font-size: 40px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 12px;
}
.welcome-title { font-size: 16px; font-weight: 700; color: #1e1e2e; margin-bottom: 8px; }
.welcome-desc  { font-size: 13px; color: #718096; margin-bottom: 20px; line-height: 1.7; }
.suggestion-list { display: flex; flex-direction: column; gap: 8px; width: 100%; max-width: 340px; }
.suggestion-btn {
  padding: 10px 14px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  color: #4b5563;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s, border-color 0.15s;
}
.suggestion-btn:hover { background: #ede9fe; border-color: #c4b5fd; color: #6366f1; }

.msg-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.msg-row-user      { flex-direction: row-reverse; }
.msg-row-assistant { flex-direction: row; }

.msg-avatar-sm {
  width: 24px;
  height: 24px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #fff;
  flex-shrink: 0;
}

.msg-bubble {
  max-width: 78%;
  padding: 10px 14px;
  border-radius: 16px;
}
.bubble-user {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.bubble-assistant {
  background: #fff;
  color: #1e1e2e;
  border-bottom-left-radius: 4px;
  border: 1px solid #e2e8f0;
}
.msg-text { font-size: 13px; line-height: 1.7; }
.msg-text :deep(code) {
  background: rgba(0,0,0,0.08);
  padding: 1px 5px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 12px;
}
.msg-text :deep(h3), .msg-text :deep(h4) { margin: 8px 0 4px; font-size: 13px; }
.msg-time { font-size: 10px; opacity: 0.5; margin-top: 5px; text-align: right; }

/* タイピングドット */
.typing-dots { display: flex; gap: 4px; padding: 4px 0; align-items: center; }
.typing-dots span {
  width: 8px; height: 8px;
  background: #a0aec0;
  border-radius: 50%;
  animation: bounce 1.2s infinite;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
  40%           { transform: translateY(-6px); opacity: 1; }
}

/* ===== エラー ===== */
.chat-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #fff5f5;
  color: #e53e3e;
  font-size: 12px;
  border-top: 1px solid #fed7d7;
  flex-shrink: 0;
}
.chat-error button {
  background: none; border: none; color: #e53e3e;
  cursor: pointer; margin-left: 8px; font-size: 12px;
}

/* ===== 入力エリア ===== */
.chat-input-area {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
  flex-shrink: 0;
}
.chat-input {
  flex: 1;
  resize: none;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 13px;
  font-family: inherit;
  line-height: 1.5;
  outline: none;
  transition: border-color 0.15s;
  min-height: 40px;
  max-height: 120px;
  overflow-y: auto;
  background: #fafafa;
}
.chat-input:focus { border-color: #6366f1; background: #fff; }
.send-btn {
  width: 36px; height: 36px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: opacity 0.15s, transform 0.15s;
}
.send-btn:disabled { opacity: 0.4; cursor: default; transform: none; }
.send-btn:not(:disabled):hover { transform: scale(1.07); }

.chat-footer {
  padding: 4px 16px 10px;
  font-size: 11px;
  color: #a0aec0;
  text-align: center;
  flex-shrink: 0;
  background: #fff;
}
</style>
