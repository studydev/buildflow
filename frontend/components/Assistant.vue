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
 * - Multi-language support (EN/KR toggle)
 */

import { ref, computed, watch, nextTick } from 'vue'
import { marked } from 'marked'
import { apiRequest } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { useContentStore } from '@/stores/content'

// Configure marked for safe rendering
marked.setOptions({
  breaks: true,  // Convert \n to <br>
  gfm: true,     // GitHub Flavored Markdown
})

// =============================================================================
// Types
// =============================================================================

interface Citation {
  content_id: string
  title: string
  title_kr?: string
  relevance: number
  description?: string
  description_kr?: string
  url?: string
  source_type?: string  // 'github' or 'youtube'
  thumbnail_url?: string
}

interface SuggestedContent {
  content_id: string
  title: string
  title_kr?: string
  description?: string
  description_kr?: string
  relevance: number
  reason?: string
  url?: string  // GitHub repo URL or YouTube URL
  source_type?: string  // 'github' or 'youtube'
  thumbnail_url?: string
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
const contentStore = useContentStore()

const isOpen = ref(false)
const isLoading = ref(false)
const error = ref<string | null>(null)
const inputMessage = ref('')
const messages = ref<ChatMessage[]>([])
const conversationId = ref<string | null>(null)
const chatContainer = ref<HTMLElement | null>(null)

// Check if user is authenticated
const isAuthenticated = computed(() => authStore.isAuthenticated)

// Language preference (kr as default when ambiguous)
const isKorean = computed(() => contentStore.displayLanguage === 'ko')

// Helper functions for localized content
function getLocalizedTitle(item: { title: string; title_kr?: string }): string {
  if (isKorean.value) {
    return item.title_kr || item.title
  }
  return item.title || item.title_kr || ''
}

function getLocalizedDescription(item: { description?: string; description_kr?: string }): string {
  if (isKorean.value) {
    return item.description_kr || item.description || ''
  }
  return item.description || item.description_kr || ''
}

// =============================================================================
// Methods
// =============================================================================

function generateId(): string {
  return Math.random().toString(36).substring(2, 15)
}

function toggleChat() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    // 채팅창을 열 때마다 대화 초기화
    messages.value = []
    conversationId.value = null
    error.value = null
    
    // Add welcome message
    messages.value.push({
      id: generateId(),
      role: 'assistant',
      content: 'Ask me anything about Azure learning content! I can help you find relevant resources and recommend learning paths.',
      timestamp: new Date(),
    })
  }
}

async function sendMessage() {
  if (!inputMessage.value.trim() || isLoading.value) return
  if (!isAuthenticated.value) {
    error.value = 'Please sign in to continue.'
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
    const response = await apiRequest<ChatResponse>('/assistant/chat', {
      method: 'POST',
      body: JSON.stringify({
        message: userMessage,
        conversation_id: conversationId.value,
        context: props.contentId ? {
          current_content_id: props.contentId,
        } : undefined,
      }),
    })

    if (response) {
      conversationId.value = response.conversation_id

      // Add assistant response
      messages.value.push({
        id: generateId(),
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        citations: response.citations,
        suggestedContent: response.suggested_content,
        externalResults: response.external_results,
      })
    }
  } catch (err: any) {
    error.value = err.message || 'Failed to get a response.'
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

function clearChat() {
  messages.value = []
  conversationId.value = null
  error.value = null
  
  // Re-add welcome message
  messages.value.push({
    id: generateId(),
    role: 'assistant',
    content: 'Ask me anything about Azure learning content! I can help you find relevant resources and recommend learning paths.',
    timestamp: new Date(),
  })
}

function handleKeyPress(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// Format citation references in text and convert markdown to HTML
function formatMessageWithCitations(content: string): string {
  // First replace [Source: xxx] with styled citations
  const withCitations = content.replace(
    /\[Source:\s*([^\]]+)\]/g,
    '<span class="citation-ref" data-id="$1">[📚]</span>'
  )
  
  // Convert markdown to HTML
  let html = marked.parse(withCitations) as string
  
  // Convert H2 to H3 for better visual hierarchy
  html = html.replace(/<h2/g, '<h3').replace(/<\/h2>/g, '</h3>')
  
  return html
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
      class="fixed bottom-24 right-6 w-[576px] max-w-[calc(100vw-3rem)] h-[calc(100vh-96px-10px-82px)] bg-white dark:bg-gray-800 rounded-lg shadow-2xl flex flex-col z-50 border border-gray-200 dark:border-gray-700"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-blue-600 text-white rounded-t-lg">
        <div class="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <span class="font-semibold">NexusSkill Assistant</span>
        </div>
        <button
          @click="clearChat"
          class="text-white/80 hover:text-white text-sm"
          title="Clear conversation"
        >
          Clear
        </button>
      </div>

      <!-- Auth Warning -->
      <div
        v-if="!isAuthenticated"
        class="px-4 py-3 bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-800 text-yellow-800 dark:text-yellow-200 text-sm"
      >
        ⚠️ Please sign in to use the assistant.
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
            'max-w-[90%] rounded-xl p-4 shadow-sm',
            message.role === 'user'
              ? 'ml-auto bg-gradient-to-r from-blue-500 to-blue-600 text-white'
              : 'mr-auto bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700'
          ]"
        >
          <!-- Message Content -->
          <div
            :class="[
              'text-sm',
              message.role === 'assistant' ? 'markdown-content' : 'whitespace-pre-wrap'
            ]"
            v-html="message.role === 'assistant' ? formatMessageWithCitations(message.content) : message.content"
          />

          <!-- Citations -->
          <div
            v-if="message.citations && message.citations.length > 0"
            class="mt-3 pt-2 border-t border-gray-200 dark:border-gray-600"
          >
            <p class="text-xs font-semibold mb-2 text-gray-600 dark:text-gray-300">📚 References:</p>
            <div class="space-y-2">
              <div
                v-for="citation in message.citations"
                :key="citation.content_id"
                class="w-full text-left p-2 rounded-lg bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/30 dark:to-orange-900/30 border border-amber-200 dark:border-amber-800"
              >
                <div class="flex gap-3">
                  <!-- Thumbnail (left) -->
                  <div v-if="citation.thumbnail_url" class="w-16 h-10 flex-shrink-0 rounded overflow-hidden bg-gray-100 dark:bg-gray-700">
                    <img :src="citation.thumbnail_url" :alt="citation.title" class="w-full h-full object-cover" />
                  </div>
                  <div v-else class="w-16 h-10 flex-shrink-0 rounded bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
                    <span v-if="citation.source_type === 'youtube'" class="text-red-500 text-lg">▶</span>
                    <span v-else class="text-gray-400 text-xs">📁</span>
                  </div>
                  <!-- Content (right) -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-start justify-between gap-2 mb-0.5">
                      <span class="text-xs font-medium text-amber-700 dark:text-amber-300 truncate">{{ getLocalizedTitle(citation) }}</span>
                      <span class="text-[10px] text-amber-500 dark:text-amber-400 shrink-0">({{ Math.round(citation.relevance) }} pts)</span>
                    </div>
                    <p v-if="getLocalizedDescription(citation)" class="text-[10px] text-gray-600 dark:text-gray-400 line-clamp-2 mb-1">
                      {{ getLocalizedDescription(citation) }}
                    </p>
                    <a
                      v-if="citation.url"
                      :href="citation.url"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="inline-flex items-center gap-1 text-[10px] hover:underline"
                      :class="citation.source_type === 'youtube' ? 'text-red-600 dark:text-red-400' : 'text-amber-600 dark:text-amber-400'"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                      {{ citation.source_type === 'youtube' ? 'Watch on YouTube' : 'View on GitHub' }}
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Suggested Content (max 5 items with reasons) -->
          <div
            v-if="message.suggestedContent && message.suggestedContent.length > 0"
            class="mt-3 pt-2 border-t border-gray-200 dark:border-gray-600"
          >
            <p class="text-xs font-semibold mb-2 text-gray-600 dark:text-gray-300">💡 Suggested Content ({{ message.suggestedContent.length }}):</p>
            <div class="space-y-2">
              <div
                v-for="suggestion in message.suggestedContent.slice(0, 5)"
                :key="suggestion.content_id"
                class="w-full text-left p-2 rounded-lg bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/30 dark:to-indigo-900/30 border border-blue-200 dark:border-blue-800"
              >
                <div class="flex gap-3">
                  <!-- Thumbnail (left) -->
                  <div v-if="suggestion.thumbnail_url" class="w-16 h-10 flex-shrink-0 rounded overflow-hidden bg-gray-100 dark:bg-gray-700">
                    <img :src="suggestion.thumbnail_url" :alt="suggestion.title" class="w-full h-full object-cover" />
                  </div>
                  <div v-else class="w-16 h-10 flex-shrink-0 rounded bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
                    <span v-if="suggestion.source_type === 'youtube'" class="text-red-500 text-lg">▶</span>
                    <span v-else class="text-gray-400 text-xs">📁</span>
                  </div>
                  <!-- Content (right) -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-start justify-between gap-2 mb-0.5">
                      <span class="text-xs font-medium text-blue-700 dark:text-blue-300 truncate">{{ getLocalizedTitle(suggestion) }}</span>
                      <span class="text-[10px] text-blue-500 dark:text-blue-400 shrink-0">{{ Math.round(suggestion.relevance) }} pts</span>
                    </div>
                    <p v-if="suggestion.reason" class="text-[10px] text-gray-600 dark:text-gray-400 line-clamp-2 mb-1">
                      {{ suggestion.reason }}
                    </p>
                    <p v-else-if="getLocalizedDescription(suggestion)" class="text-[10px] text-gray-600 dark:text-gray-400 line-clamp-2 mb-1">
                      {{ getLocalizedDescription(suggestion) }}
                    </p>
                    <a
                      v-if="suggestion.url"
                      :href="suggestion.url"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="inline-flex items-center gap-1 text-[10px] hover:underline"
                      :class="suggestion.source_type === 'youtube' ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'"
                      @click.stop
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                      {{ suggestion.source_type === 'youtube' ? 'Watch on YouTube' : 'View on GitHub' }}
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- External Results (Fallback) -->
          <div
            v-if="message.externalResults && message.externalResults.length > 0"
            class="mt-3 pt-2 border-t border-gray-200 dark:border-gray-600"
          >
            <p class="text-xs font-semibold mb-2 text-gray-600 dark:text-gray-300">🌐 External Search Results:</p>
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
            <span class="text-sm text-gray-500 dark:text-gray-400">Thinking...</span>
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
            placeholder="Type a message..."
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

/* Markdown content styling */
:deep(.markdown-content) {
  line-height: 1.6;
}

:deep(.markdown-content h1) {
  font-size: 1.25rem;
  font-weight: 700;
  margin-top: 1rem;
  margin-bottom: 0.5rem;
}

:deep(.markdown-content h2) {
  font-size: 1.1rem;
  font-weight: 600;
  margin-top: 0.875rem;
  margin-bottom: 0.375rem;
  color: #2563eb;
}

:deep(.markdown-content h3) {
  font-size: 1rem;
  font-weight: 600;
  margin-top: 0.75rem;
  margin-bottom: 0.25rem;
  color: #2563eb;
}

:deep(.markdown-content p) {
  margin-bottom: 0.5rem;
}

:deep(.markdown-content ul),
:deep(.markdown-content ol) {
  margin-left: 1.25rem;
  margin-bottom: 0.5rem;
}

:deep(.markdown-content li) {
  margin-bottom: 0.25rem;
}

:deep(.markdown-content strong) {
  font-weight: 600;
  color: #1e40af;
}

:deep(.markdown-content code) {
  background-color: rgba(0, 0, 0, 0.1);
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-size: 0.875em;
  font-family: ui-monospace, monospace;
}

:deep(.markdown-content pre) {
  background-color: rgba(0, 0, 0, 0.1);
  padding: 0.5rem;
  border-radius: 0.375rem;
  overflow-x: auto;
  margin-bottom: 0.5rem;
}

:deep(.markdown-content pre code) {
  background: none;
  padding: 0;
}

:deep(.markdown-content blockquote) {
  border-left: 3px solid #3b82f6;
  padding-left: 0.75rem;
  margin-left: 0;
  margin-bottom: 0.5rem;
  color: #6b7280;
  font-style: italic;
}

:deep(.markdown-content hr) {
  border: none;
  border-top: 1px solid #e5e7eb;
  margin: 0.75rem 0;
}

:deep(.markdown-content a) {
  color: #2563eb;
  text-decoration: underline;
}

:deep(.markdown-content a:hover) {
  color: #1d4ed8;
}

/* Dark mode adjustments */
.dark :deep(.markdown-content h2) {
  color: #60a5fa;
}

.dark :deep(.markdown-content strong) {
  color: #93c5fd;
}

.dark :deep(.markdown-content code) {
  background-color: rgba(255, 255, 255, 0.1);
}

.dark :deep(.markdown-content pre) {
  background-color: rgba(255, 255, 255, 0.1);
}

.dark :deep(.markdown-content blockquote) {
  color: #9ca3af;
}

.dark :deep(.markdown-content hr) {
  border-top-color: #4b5563;
}

.dark :deep(.markdown-content a) {
  color: #60a5fa;
}
</style>
