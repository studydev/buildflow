<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useYouTubeStore, type YouTubeRequest, type YouTubeContent } from '@/stores/youtube'
import { useContentStore } from '@/stores/content'
import LanguageToggle from '@/components/LanguageToggle.vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

// YouTube Store
const youtubeStore = useYouTubeStore()

// Content Store (for language preference)
const contentStore = useContentStore()

// Localized text helper function
const getLocalizedText = (
  enText: string | undefined, 
  krText: string | undefined,
  fallback: string = ''
): string => {
  const lang = contentStore.displayLanguage
  if (lang === 'ko') {
    return krText || enText || fallback
  }
  return enText || krText || fallback
}

// URL Input State
const youtubeUrl = ref('')
const urlError = ref('')

// URL validation for YouTube
const isValidYouTubeUrl = (url: string): boolean => {
  const patterns = [
    /^https?:\/\/(www\.)?youtube\.com\/watch\?v=[\w-]+/,
    /^https?:\/\/youtu\.be\/[\w-]+/,
    /^https?:\/\/(www\.)?youtube\.com\/embed\/[\w-]+/,
  ]
  return patterns.some(pattern => pattern.test(url))
}

// Handle URL submit
const handleUrlSubmit = async () => {
  urlError.value = ''
  
  if (!youtubeUrl.value.trim()) {
    urlError.value = 'Please enter a YouTube URL'
    return
  }
  
  if (!isValidYouTubeUrl(youtubeUrl.value.trim())) {
    urlError.value = 'Please enter a valid YouTube URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID)'
    return
  }
  
  const newRequest = await youtubeStore.submitRequest(youtubeUrl.value.trim())
  
  if (newRequest) {
    youtubeUrl.value = ''
  }
}

// Edit Modal State
const isEditModalOpen = ref(false)
const editingItem = ref<YouTubeContent | null>(null)
const isSaving = ref(false)

// UI State
const activeTab = ref<'analysis' | 'content'>('analysis')

// Format duration (seconds to mm:ss or hh:mm:ss)
function formatDuration(seconds: number): string {
  if (!seconds) return '0:00'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

// Format view count
function formatViewCount(count: number): string {
  if (!count) return '0'
  if (count >= 1000000) {
    return (count / 1000000).toFixed(1).replace(/\.0$/, '') + 'M'
  }
  if (count >= 1000) {
    return (count / 1000).toFixed(1).replace(/\.0$/, '') + 'K'
  }
  return count.toString()
}

const searchQuery = ref('')
const contentSearchQuery = ref('')
const statusFilter = ref<string | null>(null)
const expandedRequests = ref<Set<string>>(new Set())
const refreshingRequests = ref<Set<string>>(new Set())
const refreshingContents = ref<Set<string>>(new Set())

// Computed
const filteredAnalysisRequests = computed(() => {
  let requests = youtubeStore.requests
  
  if (statusFilter.value) {
    requests = requests.filter(r => r.status === statusFilter.value)
  }
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    requests = requests.filter(r => 
      r.source_url.toLowerCase().includes(query) ||
      r.result?.title?.toLowerCase().includes(query) ||
      r.result?.channel_name?.toLowerCase().includes(query)
    )
  }
  
  return requests
})

// Pagination computed values for content list
const currentPage = computed(() => youtubeStore.contentsPagination.page)
const totalPages = computed(() => Math.ceil(youtubeStore.contentsPagination.total / youtubeStore.contentsPagination.limit) || 1)
// totalItems is available via youtubeStore.contentsPagination.total if needed

// Generate page numbers to display
const visiblePages = computed(() => {
  const current = currentPage.value
  const total = totalPages.value
  const pages: (number | string)[] = []
  
  if (total <= 7) {
    for (let i = 1; i <= total; i++) {
      pages.push(i)
    }
  } else {
    pages.push(1)
    if (current > 3) pages.push('...')
    const start = Math.max(2, current - 1)
    const end = Math.min(total - 1, current + 1)
    for (let i = start; i <= end; i++) {
      pages.push(i)
    }
    if (current < total - 2) pages.push('...')
    pages.push(total)
  }
  return pages
})

function goToPage(page: number) {
  if (page >= 1 && page <= totalPages.value) {
    youtubeStore.fetchContents({ page })
  }
}

// Pagination computed values for analysis requests
const analysisCurrentPage = computed(() => youtubeStore.requestsPagination.page)
const analysisTotalPages = computed(() => Math.ceil(youtubeStore.requestsPagination.total / youtubeStore.requestsPagination.limit) || 1)
const analysisTotalItems = computed(() => youtubeStore.requestsPagination.total)

const analysisVisiblePages = computed(() => {
  const current = analysisCurrentPage.value
  const total = analysisTotalPages.value
  const pages: (number | string)[] = []
  
  if (total <= 7) {
    for (let i = 1; i <= total; i++) {
      pages.push(i)
    }
  } else {
    pages.push(1)
    if (current > 3) pages.push('...')
    const start = Math.max(2, current - 1)
    const end = Math.min(total - 1, current + 1)
    for (let i = start; i <= end; i++) {
      pages.push(i)
    }
    if (current < total - 2) pages.push('...')
    pages.push(total)
  }
  return pages
})

function goToAnalysisPage(page: number) {
  if (page >= 1 && page <= analysisTotalPages.value) {
    youtubeStore.fetchRequests({ page })
  }
}

// Status badge styling
const getStatusBadgeClass = (status: string) => {
  const classes: Record<string, string> = {
    pending: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    fetching: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    transcript: 'bg-cyan-500/10 text-cyan-600 border-cyan-500/20',
    parsing: 'bg-purple-500/10 text-purple-600 border-purple-500/20',
    completed: 'bg-green-500/10 text-green-600 border-green-500/20',
    failed: 'bg-red-500/10 text-red-600 border-red-500/20',
  }
  return classes[status] || 'bg-gray-500/10 text-gray-600 border-gray-500/20'
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    pending: 'Pending',
    fetching: 'Fetching...',
    transcript: 'Getting transcript...',
    parsing: 'Analyzing...',
    completed: 'Completed',
    failed: 'Failed',
  }
  return labels[status] || status
}

// Extract video title from URL (fallback)
const getVideoIdFromUrl = (url: string) => {
  const match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]+)/)
  return match ? match[1] : url
}

// Format date
const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// Actions
const handleRetry = async (request: YouTubeRequest) => {
  await youtubeStore.retryRequest(request.id)
}

const handleDelete = async (request: YouTubeRequest) => {
  if (confirm('Are you sure you want to delete this request?')) {
    await youtubeStore.deleteRequest(request.id)
  }
}

// Refresh metadata from YouTube API
const handleRefreshMetadata = async (requestId: string) => {
  if (refreshingRequests.value.has(requestId)) return
  
  refreshingRequests.value.add(requestId)
  try {
    const result = await youtubeStore.refreshRequestMetadata(requestId)
    if (result) {
      // Success - data is already updated in store
      console.log(`Metadata refreshed: ${result.updated_sources.join(', ')}`)
    }
  } finally {
    refreshingRequests.value.delete(requestId)
  }
}

// Refresh metadata for content
const handleRefreshContentMetadata = async (contentId: string) => {
  if (refreshingContents.value.has(contentId)) return
  
  refreshingContents.value.add(contentId)
  try {
    const result = await youtubeStore.refreshContentMetadata(contentId)
    if (result) {
      console.log(`Content metadata refreshed: ${result.updated_sources.join(', ')}`)
    }
  } finally {
    refreshingContents.value.delete(contentId)
  }
}

// Edit content generated from analysis
const handleEditContent = async (contentId: string) => {
  const content = await youtubeStore.getContentById(contentId)
  if (content) {
    openEditModal(content)
  } else {
    alert('Failed to load content.')
  }
}

// Publish content from analysis
const handlePublishContent = async (contentId: string) => {
  if (!confirm('Do you want to publish this content?')) return
  
  const result = await youtubeStore.publishContent(contentId)
  if (result) {
    alert('Content has been published.')
    await youtubeStore.fetchContents()
  } else {
    alert('Failed to publish: ' + (youtubeStore.error || 'Unknown error'))
  }
}

// Unpublish content
const handleUnpublishContent = async (contentId: string) => {
  if (!confirm('Do you want to unpublish this content?')) return
  
  const result = await youtubeStore.unpublishContent(contentId)
  if (result) {
    alert('Content has been unpublished.')
    await youtubeStore.fetchContents()
  } else {
    alert('Failed to unpublish: ' + (youtubeStore.error || 'Unknown error'))
  }
}

// Delete content
const handleDeleteContent = async (contentId: string) => {
  if (!confirm('Do you want to permanently delete this content?\n\n⚠️ This action cannot be undone!')) return
  
  const result = await youtubeStore.deleteContent(contentId)
  if (result) {
    await youtubeStore.fetchContents()
  } else {
    alert('Failed to delete: ' + (youtubeStore.error || 'Unknown error'))
  }
}

const toggleExpand = (requestId: string) => {
  if (expandedRequests.value.has(requestId)) {
    expandedRequests.value.delete(requestId)
  } else {
    expandedRequests.value.add(requestId)
  }
}

const isExpanded = (requestId: string) => {
  return expandedRequests.value.has(requestId)
}

// Open edit modal with content item
const openEditModal = (item: YouTubeContent) => {
  editingItem.value = { ...item }
  isEditModalOpen.value = true
}

// Save edit via API
const saveEdit = async () => {
  if (!editingItem.value || !editingItem.value.id) {
    isEditModalOpen.value = false
    return
  }
  
  isSaving.value = true
  
  try {
    const result = await youtubeStore.updateContent(editingItem.value.id, {
      title_en: editingItem.value.title_en,
      title_kr: editingItem.value.title_kr,
      description_en: editingItem.value.description_en,
      description_kr: editingItem.value.description_kr,
      script_summary_en: editingItem.value.script_summary_en,
      script_summary_kr: editingItem.value.script_summary_kr,
      categories: editingItem.value.categories,
      technologies: editingItem.value.technologies,
      level: editingItem.value.level,
    })
    
    if (result) {
      isEditModalOpen.value = false
      editingItem.value = null
      await youtubeStore.fetchContents()
    } else {
      alert('Failed to save changes: ' + (youtubeStore.error || 'Unknown error'))
    }
  } catch (e) {
    console.error('Failed to save edit:', e)
    alert('Failed to save changes')
  } finally {
    isSaving.value = false
  }
}

// Open URL in new tab
const openUrl = (url: string) => {
  window.open(url, '_blank')
}

// Pending requests count
const pendingRequestsCount = computed(() => {
  return youtubeStore.requests.filter(r => 
    ['pending', 'fetching', 'transcript', 'parsing'].includes(r.status)
  ).length
})

// Lifecycle
onMounted(() => {
  youtubeStore.fetchRequests()
  youtubeStore.fetchContents()
})

onUnmounted(() => {
  youtubeStore.stopPolling()
})
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-8 flex items-start justify-between">
      <div>
        <h1 class="font-header text-3xl font-bold text-[var(--text-primary)] mb-2">
          YouTube
        </h1>
        <p class="text-[var(--text-secondary)]">
          Collect content from YouTube videos and manage it on this platform.
        </p>
      </div>
      <LanguageToggle />
    </div>

    <!-- Tab Navigation -->
    <div class="flex gap-1 mb-6 border-b border-[var(--border)]">
      <button
        @click="activeTab = 'analysis'"
        :class="[
          'px-4 py-3 text-sm font-header font-medium transition-colors relative',
          activeTab === 'analysis' 
            ? 'text-primary' 
            : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
        ]"
      >
        Request Analysis
        <span v-if="pendingRequestsCount > 0" class="ml-1.5 px-1.5 py-0.5 bg-primary/10 text-primary text-xs rounded-full">
          {{ pendingRequestsCount }}
        </span>
        <span v-if="activeTab === 'analysis'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-primary"></span>
      </button>
      <button
        @click="activeTab = 'content'"
        :class="[
          'px-4 py-3 text-sm font-header font-medium transition-colors relative',
          activeTab === 'content' 
            ? 'text-primary' 
            : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
        ]"
      >
        Manage Content
        <span v-if="activeTab === 'content'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-primary"></span>
      </button>
    </div>

    <!-- Analysis Requests Tab -->
    <div v-if="activeTab === 'analysis'" class="space-y-6">
      <!-- YouTube URL input form -->
      <div class="card p-6">
        <h2 class="font-header text-lg font-semibold text-[var(--text-primary)] mb-4">
          YouTube Video URL
        </h2>
        
        <form @submit.prevent="handleUrlSubmit" class="space-y-3">
          <div class="flex gap-3">
            <!-- YouTube-only button -->
            <button
              type="button"
              class="flex items-center gap-2 px-4 py-2.5 bg-red-500/10 border border-red-500/30 text-red-500 rounded-lg font-medium"
            >
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
              YouTube
            </button>
            
            <input
              v-model="youtubeUrl"
              type="url"
              placeholder="https://www.youtube.com/watch?v=VIDEO_ID"
              class="flex-1 px-4 py-2.5 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
              :class="{ 'border-red-500 focus:border-red-500': urlError }"
              :disabled="youtubeStore.isSubmitting"
            />
            <button 
              type="submit" 
              class="px-6 py-2.5 bg-primary hover:bg-primary-hover text-white font-header font-semibold rounded-lg transition-colors disabled:opacity-50"
              :disabled="youtubeStore.isSubmitting"
            >
              <span v-if="youtubeStore.isSubmitting" class="flex items-center gap-2">
                <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Submitting...
              </span>
              <span v-else>Request Analysis</span>
            </button>
          </div>
          
          <p v-if="urlError" class="text-sm text-red-500">{{ urlError }}</p>
          <p v-else-if="youtubeStore.error" class="text-sm text-red-500">{{ youtubeStore.error }}</p>
          <p v-else class="text-sm text-[var(--text-tertiary)]">
            💡 The video's metadata and transcript will be analyzed to automatically extract content information.
          </p>
        </form>
      </div>

      <!-- Search and Filters -->
      <div class="flex gap-4 items-center">
        <div class="relative flex-1 max-w-md">
          <svg 
            class="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" 
            width="20" 
            height="20" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search by URL or title..."
            class="w-full pl-11 pr-4 py-2.5 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
          />
        </div>
        
        <div class="flex gap-2">
          <button
            @click="statusFilter = null"
            :class="[
              'px-3 py-2 rounded-lg text-sm font-header font-medium transition-colors',
              statusFilter === null 
                ? 'bg-primary text-white' 
                : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-primary hover:text-primary'
            ]"
          >
            All
          </button>
          <button
            @click="statusFilter = 'pending'"
            :class="[
              'px-3 py-2 rounded-lg text-sm font-header font-medium transition-colors',
              statusFilter === 'pending' 
                ? 'bg-yellow-500 text-white' 
                : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-yellow-500 hover:text-yellow-500'
            ]"
          >
            Pending
          </button>
          <button
            @click="statusFilter = 'completed'"
            :class="[
              'px-3 py-2 rounded-lg text-sm font-header font-medium transition-colors',
              statusFilter === 'completed' 
                ? 'bg-green-500 text-white' 
                : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-green-500 hover:text-green-500'
            ]"
          >
            Completed
          </button>
          <button
            @click="statusFilter = 'failed'"
            :class="[
              'px-3 py-2 rounded-lg text-sm font-header font-medium transition-colors',
              statusFilter === 'failed' 
                ? 'bg-red-500 text-white' 
                : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-red-500 hover:text-red-500'
            ]"
          >
            Failed
          </button>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="youtubeStore.isLoading" class="text-center py-12">
        <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <p class="mt-4 text-[var(--text-secondary)]">Loading analysis requests...</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="youtubeStore.requests.length === 0" class="text-center py-12">
        <svg class="mx-auto h-12 w-12 text-[var(--text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 class="mt-4 text-lg font-header font-semibold text-[var(--text-primary)]">No analysis requests yet</h3>
        <p class="mt-2 text-[var(--text-secondary)]">Enter a YouTube video URL above to start content analysis</p>
      </div>

      <!-- Analysis Requests Table -->
      <div v-else class="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl overflow-hidden">
        <table class="w-full">
          <thead>
            <tr class="bg-[var(--bg-secondary)] border-b border-[var(--border)]">
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Video</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Status</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Progress</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Submitted</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Result</th>
              <th class="px-4 py-3 text-right text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--border)]">
            <template v-for="request in filteredAnalysisRequests" :key="request.id">
              <tr class="hover:bg-[var(--bg-secondary)]/50 transition-colors">
                <!-- Video -->
                <td class="px-4 py-4">
                  <a 
                    :href="request.source_url" 
                    target="_blank" 
                    class="text-sm font-medium text-primary hover:underline flex items-center gap-2"
                  >
                    <svg class="w-4 h-4 flex-shrink-0 text-red-500" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                    </svg>
                    <span class="truncate max-w-[200px]">
                      {{ getLocalizedText(request.result?.title_en || request.result?.title, request.result?.title_kr) || getVideoIdFromUrl(request.source_url) }}
                    </span>
                  </a>
                  <p v-if="request.result?.channel_name" class="text-xs text-[var(--text-tertiary)] mt-0.5">
                    {{ request.result.channel_name }}
                  </p>
                </td>
                
                <!-- Status -->
                <td class="px-4 py-4">
                  <span :class="['inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border', getStatusBadgeClass(request.status)]">
                    <span v-if="['pending', 'fetching', 'transcript', 'parsing'].includes(request.status)" class="w-2 h-2 mr-1.5 rounded-full bg-current animate-pulse"></span>
                    {{ getStatusLabel(request.status) }}
                  </span>
                </td>
                
                <!-- Progress -->
                <td class="px-4 py-4">
                  <div class="flex items-center gap-2">
                    <div class="flex-1 h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden max-w-[100px]">
                      <div 
                        class="h-full bg-primary transition-all duration-500"
                        :style="{ width: `${request.progress}%` }"
                      ></div>
                    </div>
                    <span class="text-xs text-[var(--text-secondary)] tabular-nums">{{ request.progress }}%</span>
                  </div>
                </td>
                
                <!-- Created Date -->
                <td class="px-4 py-4 text-sm text-[var(--text-secondary)]">
                  {{ formatDate(request.created_at) }}
                </td>
                
                <!-- Result -->
                <td class="px-4 py-4">
                  <template v-if="request.status === 'completed' && request.result">
                    <button
                      @click="toggleExpand(request.id)"
                      class="flex items-center gap-2 text-sm group"
                    >
                      <svg 
                        :class="['w-4 h-4 text-[var(--text-tertiary)] transition-transform', isExpanded(request.id) ? 'rotate-90' : '']" 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                      </svg>
                      <div class="text-left">
                        <p class="font-medium text-[var(--text-primary)] truncate max-w-[180px] group-hover:text-primary transition-colors">
                          {{ formatDuration(request.result.duration_seconds) }}
                        </p>
                        <p class="text-xs text-[var(--text-secondary)]">
                          {{ formatViewCount(request.result.view_count) }} views
                        </p>
                      </div>
                    </button>
                  </template>
                  <template v-else-if="request.status === 'failed'">
                    <button
                      @click="toggleExpand(request.id)"
                      class="flex items-center gap-2 text-sm group text-left"
                    >
                      <svg 
                        :class="['w-4 h-4 text-red-400 transition-transform', isExpanded(request.id) ? 'rotate-90' : '']" 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                      </svg>
                      <span class="text-red-500 truncate max-w-[180px] group-hover:underline" :title="request.error_message">
                        {{ request.error_message || 'Analysis failed' }}
                      </span>
                    </button>
                  </template>
                  <template v-else>
                    <span class="text-sm text-[var(--text-tertiary)]">-</span>
                  </template>
                </td>
                
                <!-- Actions -->
                <td class="px-4 py-4 text-right">
                  <div class="flex items-center justify-end gap-2">
                    <template v-if="request.status === 'completed'">
                      <button
                        v-if="request.content_id"
                        @click="handleEditContent(request.content_id)"
                        class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-primary hover:bg-primary/10 transition-colors"
                        title="Edit content"
                      >
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                        </svg>
                      </button>
                      <button
                        v-if="request.content_id"
                        @click="handlePublishContent(request.content_id)"
                        class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-green-500 hover:bg-green-500/10 transition-colors"
                        title="Publish content"
                      >
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                        </svg>
                      </button>
                    </template>
                    <template v-if="request.status === 'failed'">
                      <button
                        @click="handleRetry(request)"
                        class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-blue-500 hover:bg-blue-500/10 transition-colors"
                        title="Retry analysis"
                      >
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                        </svg>
                      </button>
                    </template>
                    <button
                      @click="handleDelete(request)"
                      class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
                      title="Delete request"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>
              
              <!-- Expanded Details Row -->
              <tr v-if="isExpanded(request.id) && request.status === 'completed' && request.result">
                <td colspan="6" class="px-4 py-4 bg-[var(--bg-secondary)]/30">
                  <div class="flex gap-6">
                    <!-- Thumbnail -->
                    <div v-if="request.result.thumbnail_url" class="w-48 flex-shrink-0">
                      <img
                        :src="request.result.thumbnail_url"
                        :alt="request.result.title"
                        class="w-full aspect-video object-cover rounded-lg"
                      />
                    </div>
                    
                    <!-- Details -->
                    <div class="flex-1 space-y-3">
                      <div>
                        <h4 class="font-medium text-[var(--text-primary)]">{{ getLocalizedText(request.result.title_en || request.result.title, request.result.title_kr) }}</h4>
                        <p class="text-sm font-semibold text-[var(--text-secondary)] mt-1">{{ request.result.channel_name }}</p>
                      </div>
                      
                      <!-- Metrics with Refresh Button -->
                      <div class="flex flex-wrap items-center gap-4 text-sm text-[var(--text-tertiary)]">
                        <span>📺 {{ formatViewCount(request.result.view_count) }} views</span>
                        <span>👍 {{ formatViewCount(request.result.like_count) }} likes</span>
                        <span>⏱️ {{ formatDuration(request.result.duration_seconds) }}</span>
                        <button
                          @click.stop="handleRefreshMetadata(request.id)"
                          :disabled="refreshingRequests.has(request.id)"
                          class="ml-2 p-1.5 rounded-lg text-[var(--text-tertiary)] hover:text-primary hover:bg-primary/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          title="Refresh metrics from YouTube"
                        >
                          <svg 
                            :class="['w-4 h-4', refreshingRequests.has(request.id) ? 'animate-spin' : '']" 
                            fill="none" 
                            stroke="currentColor" 
                            viewBox="0 0 24 24"
                          >
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                          </svg>
                        </button>
                      </div>
                      
                      <!-- Description -->
                      <div v-if="request.result.description_en || request.result.description_kr || request.result.description" class="space-y-1">
                        <p class="text-xs font-medium text-[var(--text-tertiary)]">Description</p>
                        <p class="text-sm text-[var(--text-secondary)] line-clamp-3">
                          {{ getLocalizedText(request.result.description_en || request.result.description, request.result.description_kr) }}
                        </p>
                      </div>
                      
                      <!-- Categories -->
                      <div v-if="request.result.categories?.length" class="flex flex-wrap gap-1">
                        <span
                          v-for="cat in request.result.categories"
                          :key="cat"
                          class="px-2 py-0.5 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-xs rounded-full"
                        >
                          {{ cat }}
                        </span>
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
              
              <!-- Error Details Row -->
              <tr v-if="isExpanded(request.id) && request.status === 'failed'">
                <td colspan="6" class="px-4 py-4 bg-red-500/5">
                  <div class="text-sm text-red-500">
                    <p class="font-medium">Error Details:</p>
                    <p class="mt-1">{{ request.error_message }}</p>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
        
        <!-- Pagination -->
        <div v-if="analysisTotalPages > 1" class="flex items-center justify-between px-4 py-3 border-t border-[var(--border)]">
          <p class="text-sm text-[var(--text-tertiary)]">
            Showing {{ (analysisCurrentPage - 1) * youtubeStore.requestsPagination.limit + 1 }} - {{ Math.min(analysisCurrentPage * youtubeStore.requestsPagination.limit, analysisTotalItems) }} of {{ analysisTotalItems }}
          </p>
          <div class="flex gap-1">
            <button
              @click="goToAnalysisPage(analysisCurrentPage - 1)"
              :disabled="analysisCurrentPage <= 1"
              class="p-2 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--bg-tertiary)]"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
              </svg>
            </button>
            <template v-for="page in analysisVisiblePages" :key="page">
              <span v-if="page === '...'" class="px-3 py-2 text-[var(--text-tertiary)]">...</span>
              <button
                v-else
                @click="goToAnalysisPage(page as number)"
                :class="[
                  'px-3 py-2 rounded-lg text-sm font-medium',
                  page === analysisCurrentPage ? 'bg-primary text-white' : 'hover:bg-[var(--bg-tertiary)]'
                ]"
              >
                {{ page }}
              </button>
            </template>
            <button
              @click="goToAnalysisPage(analysisCurrentPage + 1)"
              :disabled="analysisCurrentPage >= analysisTotalPages"
              class="p-2 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--bg-tertiary)]"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Content Management Tab -->
    <div v-if="activeTab === 'content'" class="space-y-6">
      <!-- Search -->
      <div class="relative max-w-md">
        <svg 
          class="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" 
          width="20" 
          height="20" 
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <input
          v-model="contentSearchQuery"
          type="text"
          placeholder="Search content..."
          class="w-full pl-11 pr-4 py-2.5 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
        />
      </div>

      <!-- Loading State -->
      <div v-if="youtubeStore.isLoading" class="text-center py-12">
        <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <p class="mt-4 text-[var(--text-secondary)]">Loading content...</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="youtubeStore.contents.length === 0" class="text-center py-12">
        <svg class="mx-auto h-12 w-12 text-[var(--text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 class="mt-4 text-lg font-header font-semibold text-[var(--text-primary)]">No content yet</h3>
        <p class="mt-2 text-[var(--text-secondary)]">Analyze YouTube videos to create content</p>
      </div>

      <!-- Content Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div
          v-for="content in youtubeStore.contents"
          :key="content.id"
          class="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl overflow-hidden hover:border-primary/50 transition-all"
        >
          <!-- Thumbnail -->
          <div class="relative aspect-video bg-[var(--bg-tertiary)]">
            <img
              v-if="content.thumbnail_url"
              :src="content.thumbnail_url"
              :alt="content.title"
              class="w-full h-full object-cover"
            />
            <div v-else class="w-full h-full flex items-center justify-center">
              <svg class="w-12 h-12 text-[var(--text-tertiary)]" fill="currentColor" viewBox="0 0 24 24">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
            </div>
            <!-- Duration badge -->
            <div class="absolute bottom-2 right-2 bg-black/80 text-white text-xs px-1.5 py-0.5 rounded">
              {{ formatDuration(content.duration_seconds) }}
            </div>
            <!-- View count badge (bottom left) -->
            <div v-if="content.view_count" class="absolute bottom-2 left-2 flex items-center gap-1 px-2 py-1 bg-black/60 backdrop-blur-sm rounded-md text-white text-xs">
              <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
              </svg>
              {{ formatViewCount(content.view_count) }} views
            </div>
            <!-- Like count badge (top right) -->
            <div v-if="content.like_count" class="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 bg-black/60 backdrop-blur-sm rounded-md text-white text-xs font-semibold">
              <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2z"/>
              </svg>
              {{ formatViewCount(content.like_count) }}
            </div>
            <!-- Status badge -->
            <div class="absolute top-2 left-2">
              <span
                :class="[
                  'px-2 py-0.5 text-xs font-medium rounded-full',
                  content.status === 'published' ? 'bg-green-500 text-white' : 'bg-yellow-500 text-black'
                ]"
              >
                {{ content.status === 'published' ? 'Published' : 'Draft' }}
              </span>
            </div>
          </div>

          <!-- Content -->
          <div class="p-4">
            <h3 class="font-semibold text-[var(--text-primary)] line-clamp-2">
              {{ getLocalizedText(content.title_en, content.title_kr, content.title) }}
            </h3>
            <p v-if="content.channel_name" class="mt-1 text-sm font-semibold text-[var(--text-primary)]">
              {{ content.channel_name }}
            </p>
            <p class="mt-2 text-sm text-[var(--text-secondary)] line-clamp-5">
              {{ getLocalizedText(content.description_en, content.description_kr, content.description) }}
            </p>

            <!-- Categories -->
            <div v-if="content.categories?.length" class="mt-3 flex flex-wrap gap-1">
              <span
                v-for="cat in content.categories.slice(0, 3)"
                :key="cat"
                class="px-2 py-0.5 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-xs rounded-full"
              >
                {{ cat }}
              </span>
            </div>

            <!-- Actions -->
            <div class="mt-4 flex items-center gap-2 pt-3 border-t border-[var(--border)]">
              <button
                @click="openUrl(content.source_url)"
                class="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 bg-red-500/10 text-red-500 text-sm font-medium rounded-lg hover:bg-red-500/20 transition-colors"
              >
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
                YouTube
              </button>
              <button
                @click="openEditModal(content)"
                class="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-primary hover:bg-primary/10 transition-colors"
                title="Edit"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                </svg>
              </button>
              <button
                v-if="content.status !== 'published'"
                @click="handlePublishContent(content.id)"
                class="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-green-500 hover:bg-green-500/10 transition-colors"
                title="Publish"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
              </button>
              <button
                v-else
                @click="handleUnpublishContent(content.id)"
                class="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-yellow-500 hover:bg-yellow-500/10 transition-colors"
                title="Unpublish"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"/>
                </svg>
              </button>
              <button
                @click="handleDeleteContent(content.id)"
                class="p-1.5 rounded-lg text-[var(--text-secondary)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
                title="Delete"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-8">
        <button
          @click="goToPage(currentPage - 1)"
          :disabled="currentPage <= 1"
          class="p-2 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--bg-tertiary)]"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
          </svg>
        </button>
        <template v-for="page in visiblePages" :key="page">
          <span v-if="page === '...'" class="px-3 py-2 text-[var(--text-tertiary)]">...</span>
          <button
            v-else
            @click="goToPage(page as number)"
            :class="[
              'px-3 py-2 rounded-lg text-sm font-medium',
              page === currentPage ? 'bg-primary text-white' : 'hover:bg-[var(--bg-tertiary)]'
            ]"
          >
            {{ page }}
          </button>
        </template>
        <button
          @click="goToPage(currentPage + 1)"
          :disabled="currentPage >= totalPages"
          class="p-2 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--bg-tertiary)]"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Edit Modal -->
    <Dialog v-model:open="isEditModalOpen">
      <DialogContent class="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            Edit YouTube Content
          </DialogTitle>
          <DialogDescription>
            Edit the content details below. Fields are available in both English and Korean.
          </DialogDescription>
        </DialogHeader>

        <div v-if="editingItem" class="space-y-6 py-4">
          <!-- Preview -->
          <div class="flex gap-4 p-4 bg-[var(--bg-secondary)] rounded-lg">
            <img
              v-if="editingItem.thumbnail_url"
              :src="editingItem.thumbnail_url"
              :alt="editingItem.title"
              class="w-32 aspect-video object-cover rounded-lg"
            />
            <div>
              <h4 class="font-medium text-[var(--text-primary)]">{{ editingItem.title }}</h4>
              <p class="text-sm text-[var(--text-secondary)]">{{ editingItem.channel_name }}</p>
              <p class="text-xs text-[var(--text-tertiary)] mt-1">
                {{ formatViewCount(editingItem.view_count) }} views • {{ formatDuration(editingItem.duration_seconds) }}
              </p>
            </div>
          </div>

          <!-- Titles -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-sm font-medium text-[var(--text-secondary)]">Title (English)</label>
              <input
                v-model="editingItem.title_en"
                type="text"
                class="mt-1 w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label class="text-sm font-medium text-[var(--text-secondary)]">Title (Korean)</label>
              <input
                v-model="editingItem.title_kr"
                type="text"
                class="mt-1 w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <!-- Descriptions -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-sm font-medium text-[var(--text-secondary)]">Description (English)</label>
              <textarea
                v-model="editingItem.description_en"
                rows="3"
                class="mt-1 w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] focus:outline-none focus:border-primary resize-none"
              ></textarea>
            </div>
            <div>
              <label class="text-sm font-medium text-[var(--text-secondary)]">Description (Korean)</label>
              <textarea
                v-model="editingItem.description_kr"
                rows="3"
                class="mt-1 w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] focus:outline-none focus:border-primary resize-none"
              ></textarea>
            </div>
          </div>

          <!-- Script Summaries -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-sm font-medium text-[var(--text-secondary)]">Script Summary (English)</label>
              <textarea
                v-model="editingItem.script_summary_en"
                rows="4"
                maxlength="1000"
                class="mt-1 w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] focus:outline-none focus:border-primary resize-none"
              ></textarea>
              <p class="mt-1 text-xs text-[var(--text-tertiary)]">{{ (editingItem.script_summary_en?.length || 0) }}/1000 characters</p>
            </div>
            <div>
              <label class="text-sm font-medium text-[var(--text-secondary)]">Script Summary (Korean)</label>
              <textarea
                v-model="editingItem.script_summary_kr"
                rows="4"
                maxlength="1000"
                class="mt-1 w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] focus:outline-none focus:border-primary resize-none"
              ></textarea>
              <p class="mt-1 text-xs text-[var(--text-tertiary)]">{{ (editingItem.script_summary_kr?.length || 0) }}/1000 characters</p>
            </div>
          </div>

          <!-- Categories and Technologies -->
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-sm font-medium text-[var(--text-secondary)]">Categories (comma separated)</label>
              <input
                :value="editingItem.categories?.join(', ')"
                @input="(e) => editingItem!.categories = (e.target as HTMLInputElement).value.split(',').map(s => s.trim()).filter(Boolean)"
                type="text"
                class="mt-1 w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] focus:outline-none focus:border-primary"
                placeholder="AI, Azure, DevOps"
              />
            </div>
            <div>
              <label class="text-sm font-medium text-[var(--text-secondary)]">Technologies (comma separated)</label>
              <input
                :value="editingItem.technologies?.join(', ')"
                @input="(e) => editingItem!.technologies = (e.target as HTMLInputElement).value.split(',').map(s => s.trim()).filter(Boolean)"
                type="text"
                class="mt-1 w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] focus:outline-none focus:border-primary"
                placeholder="Python, Azure Functions"
              />
            </div>
          </div>

          <!-- Level -->
          <div>
            <label class="text-sm font-medium text-[var(--text-secondary)]">Level</label>
            <select
              v-model="editingItem.level"
              class="mt-1 w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] focus:outline-none focus:border-primary"
            >
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </div>
        </div>

        <DialogFooter>
          <button
            @click="isEditModalOpen = false"
            class="px-4 py-2 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            Cancel
          </button>
          <button
            @click="saveEdit"
            :disabled="isSaving"
            class="px-4 py-2 bg-primary hover:bg-primary-hover text-white font-medium rounded-lg disabled:opacity-50 transition-colors"
          >
            <span v-if="isSaving" class="flex items-center gap-2">
              <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Saving...
            </span>
            <span v-else>Save Changes</span>
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
