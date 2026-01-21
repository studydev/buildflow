<script setup lang="ts">
/**
 * AI Assistant Chat UI Component
 * 
 * Per design.md §8: AI Assistant Integration
 * Per tasks.md T703: Frontend assistant UI
 * 
 * Features:
 * - Chat interface with message history
 * - Citations displayed with clickable links
 * - Suggested content recommendations
 * - Loading and error states
 */

import { ref, computed, watch, nextTick } from 'vue'
import { apiRequest } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'

// =============================================================================
// Types
// =============================================================================

interface Citation {
  content_id: string
  title: string
  relevance: number
  snippet?: string
  url?: string
}

interface SuggestedContent {
  content_id: string
  title: string
  description?: string
  relevance: number
  reason?: string
}

interface ExternalResult {
  title: string
  url: string
  snippet: string
  source_type: string
  disclaimer: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  citations?: Citation[]
  suggestedContent?: SuggestedContent[]
  externalResults?: ExternalResult[]
}

interface ChatResponse {
  response: string
  citations: Citation[]
  suggested_content: SuggestedContent[]
  external_results: ExternalResult[]
  conversation_id: string
  used_external_search: boolean
}

// =============================================================================
// Props & Emits
// =============================================================================

const props = defineProps<{
  contentId?: string  // Current content being viewed
}>()

const emit = defineEmits<{
  (e: 'select-content', contentId: string): void
}>()

// =============================================================================
// State
// =============================================================================

const authStore = useAuthStore()

const isOpen = ref(false)
const isLoading = ref(false)
const error = ref<string | null>(null)
const inputMessage = ref('')
const messages = ref<ChatMessage[]>([])
const conversationId = ref<string | null>(null)
const chatContainer = ref<HTMLElement | null>(null)

// Check if user is authenticated
const isAuthenticated = computed(() => authStore.isAuthenticated)

// =============================================================================
// Methods
// =============================================================================

function generateId(): string {
  return Math.random().toString(36).substring(2, 15)
}

function toggleChat() {
  isOpen.value = !isOpen.value
  if (isOpen.value && messages.value.length === 0) {
    // Add welcome message
    messages.value.push({
      id: generateId(),
      role: 'assistant',
      content: 'Azure 학습 콘텐츠에 대해 무엇이든 물어보세요! 관련 리소스를 찾아드리고, 학습 경로를 추천해 드립니다.',
      timestamp: new Date(),
    })
  }
}

async function sendMessage() {
  if (!inputMessage.value.trim() || isLoading.value) return
  if (!isAuthenticated.value) {
    error.value = '로그인이 필요합니다.'
    return
  }

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''
  error.value = null

  // Add user message
  messages.value.push({
    id: generateId(),
    role: 'user',
    content: userMessage,
    timestamp: new Date(),
  })

  // Scroll to bottom
  await nextTick()
  scrollToBottom()

  // Send to API
  isLoading.value = true

  try {
    const response = await apiRequest<{ success: boolean; data: ChatResponse }>('/assistant/chat', {
      method: 'POST',
      body: JSON.stringify({
        message: userMessage,
        conversation_id: conversationId.value,
        context: props.contentId ? {
          current_content_id: props.contentId,
        } : undefined,
      }),
    })

    if (response.success && response.data) {
      conversationId.value = response.data.conversation_id

      // Add assistant response
      messages.value.push({
        id: generateId(),
        role: 'assistant',
        content: response.data.response,
        timestamp: new Date(),
        citations: response.data.citations,
        suggestedContent: response.data.suggested_content,
        externalResults: response.data.external_results,
      })
    }
  } catch (err: any) {
    error.value = err.message || '응답을 받는 데 실패했습니다.'
    console.error('Chat error:', err)
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function scrollToBottom() {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

function handleCitationClick(citation: Citation) {
  emit('select-content', citation.content_id)
}

function handleSuggestionClick(suggestion: SuggestedContent) {
  emit('select-content', suggestion.content_id)
}

function clearChat() {
  messages.value = []
  conversationId.value = null
  error.value = null
  
  // Re-add welcome message
  messages.value.push({
    id: generateId(),
    role: 'assistant',
    content: 'Azure 학습 콘텐츠에 대해 무엇이든 물어보세요! 관련 리소스를 찾아드리고, 학습 경로를 추천해 드립니다.',
    timestamp: new Date(),
  })
}

function handleKeyPress(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// Format citation references in text
function formatMessageWithCitations(content: string): string {
  // Replace [Source: xxx] with styled citations
  return content.replace(
    /\[Source:\s*([^\]]+)\]/g,
    '<span class="citation-ref" data-id="$1">[📚]</span>'
  )
}

// Watch for prop changes
watch(() => props.contentId, (newId) => {
  if (newId && isOpen.value) {
    // Optionally notify user about context change
  }
})
</script>

<template>
  <!-- Floating Chat Button -->
  <button
    @click="toggleChat"
    class="fixed bottom-6 right-6 w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all duration-300 z-50"
    :class="{ 'rotate-180': isOpen }"
  >
    <svg v-if="!isOpen" xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
    </svg>
    <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
    </svg>
  </button>

  <!-- Chat Panel -->
  <Transition name="slide-up">
    <div
      v-if="isOpen"
      class="fixed bottom-24 right-6 w-96 max-w-[calc(100vw-3rem)] h-[500px] bg-white dark:bg-gray-800 rounded-lg shadow-2xl flex flex-col z-50 border border-gray-200 dark:border-gray-700"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-blue-600 text-white rounded-t-lg">
        <div class="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <span class="font-semibold">BuildFlow Assistant</span>
        </div>
        <button
          @click="clearChat"
          class="text-white/80 hover:text-white text-sm"
          title="대화 초기화"
        >
          초기화
        </button>
      </div>

      <!-- Auth Warning -->
      <div
        v-if="!isAuthenticated"
        class="px-4 py-3 bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-800 text-yellow-800 dark:text-yellow-200 text-sm"
      >
        ⚠️ 어시스턴트를 사용하려면 로그인이 필요합니다.
      </div>

      <!-- Messages Container -->
      <div
        ref="chatContainer"
        class="flex-1 overflow-y-auto p-4 space-y-4"
      >
        <div
          v-for="message in messages"
          :key="message.id"
          :class="[
            'max-w-[85%] rounded-lg p-3',
            message.role === 'user'
              ? 'ml-auto bg-blue-600 text-white'
              : 'mr-auto bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-100'
          ]"
        >
          <!-- Message Content -->
          <div
            class="text-sm whitespace-pre-wrap"
            v-html="message.role === 'assistant' ? formatMessageWithCitations(message.content) : message.content"
          />

          <!-- Citations -->
          <div
            v-if="message.citations && message.citations.length > 0"
            class="mt-3 pt-2 border-t border-gray-200 dark:border-gray-600"
          >
            <p class="text-xs font-semibold mb-2 text-gray-600 dark:text-gray-300">📚 참고 자료:</p>
            <div class="space-y-1">
              <button
                v-for="citation in message.citations"
                :key="citation.content_id"
                @click="handleCitationClick(citation)"
                class="block w-full text-left text-xs p-2 rounded bg-white/50 dark:bg-gray-600/50 hover:bg-white dark:hover:bg-gray-600 transition"
              >
                <span class="font-medium text-blue-600 dark:text-blue-400">{{ citation.title }}</span>
                <span class="text-gray-500 dark:text-gray-400 ml-1">({{ Math.round(citation.relevance * 100) }}%)</span>
                <p v-if="citation.snippet" class="text-gray-600 dark:text-gray-300 truncate mt-1">
                  {{ citation.snippet }}
                </p>
              </button>
            </div>
          </div>

          <!-- Suggested Content -->
          <div
            v-if="message.suggestedContent && message.suggestedContent.length > 0"
            class="mt-3 pt-2 border-t border-gray-200 dark:border-gray-600"
          >
            <p class="text-xs font-semibold mb-2 text-gray-600 dark:text-gray-300">💡 추천 콘텐츠:</p>
            <div class="flex flex-wrap gap-1">
              <button
                v-for="suggestion in message.suggestedContent.slice(0, 3)"
                :key="suggestion.content_id"
                @click="handleSuggestionClick(suggestion)"
                class="text-xs px-2 py-1 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900 transition"
              >
                {{ suggestion.title }}
              </button>
            </div>
          </div>

          <!-- External Results (Fallback) -->
          <div
            v-if="message.externalResults && message.externalResults.length > 0"
            class="mt-3 pt-2 border-t border-gray-200 dark:border-gray-600"
          >
            <p class="text-xs font-semibold mb-2 text-gray-600 dark:text-gray-300">🌐 외부 검색 결과:</p>
            <div class="space-y-1">
              <a
                v-for="(result, idx) in message.externalResults"
                :key="idx"
                :href="result.url"
                target="_blank"
                rel="noopener noreferrer"
                class="block text-xs p-2 rounded bg-white/50 dark:bg-gray-600/50 hover:bg-white dark:hover:bg-gray-600 transition"
              >
                <span class="font-medium text-blue-600 dark:text-blue-400">{{ result.title }}</span>
                <p class="text-gray-600 dark:text-gray-300 truncate mt-1">{{ result.snippet }}</p>
                <p class="text-gray-400 text-[10px] mt-1">⚠️ {{ result.disclaimer }}</p>
              </a>
            </div>
          </div>

          <!-- Timestamp -->
          <div class="text-[10px] mt-2 opacity-60">
            {{ message.timestamp.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) }}
          </div>
        </div>

        <!-- Loading Indicator -->
        <div
          v-if="isLoading"
          class="mr-auto max-w-[85%] rounded-lg p-3 bg-gray-100 dark:bg-gray-700"
        >
          <div class="flex items-center gap-2">
            <div class="flex space-x-1">
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
            </div>
            <span class="text-sm text-gray-500 dark:text-gray-400">생각하는 중...</span>
          </div>
        </div>
      </div>

      <!-- Error Message -->
      <div
        v-if="error"
        class="px-4 py-2 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm"
      >
        {{ error }}
      </div>

      <!-- Input Area -->
      <div class="p-3 border-t border-gray-200 dark:border-gray-700">
        <div class="flex gap-2">
          <textarea
            v-model="inputMessage"
            @keypress="handleKeyPress"
            :disabled="!isAuthenticated || isLoading"
            placeholder="메시지를 입력하세요..."
            rows="1"
            class="flex-1 resize-none rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            @click="sendMessage"
            :disabled="!isAuthenticated || isLoading || !inputMessage.trim()"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white rounded-lg transition flex items-center justify-center"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

.citation-ref {
  cursor: pointer;
  color: #3b82f6;
}

.citation-ref:hover {
  text-decoration: underline;
}
</style>
