<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useAnalysisStore } from '@/stores/analysis'
import { useContentStore, type ContentItem as StoreContentItem } from '@/stores/content'
import type { AnalysisRequest } from '@/stores/analysis'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import LanguageToggle from '@/components/LanguageToggle.vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

// Analysis Store
const analysisStore = useAnalysisStore()

// Content Store (for real API operations)
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
const githubUrl = ref('')
const urlError = ref('')

// URL validation
const isValidUrl = (url: string): boolean => {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

// Handle URL submit
const handleUrlSubmit = async () => {
  urlError.value = ''
  
  if (!githubUrl.value.trim()) {
    urlError.value = 'Please enter a URL'
    return
  }
  
  if (!isValidUrl(githubUrl.value.trim())) {
    urlError.value = 'Please enter a valid URL (e.g., https://github.com/owner/repo)'
    return
  }
  
  const newRequest = await analysisStore.submitRequest(githubUrl.value.trim())
  
  if (newRequest) {
    githubUrl.value = ''
  }
}

// Edit Modal State
const isEditModalOpen = ref(false)
const editingItem = ref<StoreContentItem | null>(null)
const isSaving = ref(false)
const editLanguage = ref<'en' | 'ko'>('en')
const isRegeneratingThumbnail = ref(false)

// UI State
const activeTab = ref<'analysis' | 'content'>('analysis')

// Format star count (e.g., 1500 -> "1.5k")
function formatStars(stars: number | undefined): string {
  if (!stars) return '0'
  if (stars >= 1000) {
    return (stars / 1000).toFixed(1).replace(/\.0$/, '') + 'k'
  }
  return stars.toString()
}

// Format relative time for last commit
function formatLastCommit(dateStr: string | undefined): string {
  if (!dateStr) return ''
  
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  
  if (diffDays < 1) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 30) return `${diffDays} days ago`
  
  const diffMonths = Math.floor(diffDays / 30)
  if (diffMonths < 12) return `${diffMonths} months ago`
  
  const diffYears = Math.floor(diffMonths / 12)
  return `${diffYears} years ago`
}
const searchQuery = ref('')
const contentSearchQuery = ref('')
const statusFilter = ref<string | null>(null)
const expandedRequests = ref<Set<string>>(new Set())

// Content search handler with debounce
let searchTimeout: ReturnType<typeof setTimeout> | null = null
const onContentSearch = () => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    contentStore.search(contentSearchQuery.value)
  }, 300)
}

// Computed
const filteredAnalysisRequests = computed(() => {
  let requests = analysisStore.requests
  
  if (statusFilter.value) {
    requests = requests.filter(r => r.status === statusFilter.value)
  }
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    requests = requests.filter(r => 
      r.source_url.toLowerCase().includes(query) ||
      r.result?.title?.toLowerCase().includes(query)
    )
  }
  
  return requests
})

// Status badge styling
const getStatusBadgeClass = (status: string) => {
  const classes: Record<string, string> = {
    pending: 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20',
    fetching: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    parsing: 'bg-purple-500/10 text-purple-600 border-purple-500/20',
    generating_thumbnail: 'bg-indigo-500/10 text-indigo-600 border-indigo-500/20',
    completed: 'bg-green-500/10 text-green-600 border-green-500/20',
    failed: 'bg-red-500/10 text-red-600 border-red-500/20',
  }
  return classes[status] || 'bg-gray-500/10 text-gray-600 border-gray-500/20'
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    pending: 'Pending',
    fetching: 'Fetching...',
    parsing: 'Analyzing...',
    generating_thumbnail: 'Generating thumbnail...',
    completed: 'Completed',
    failed: 'Failed',
  }
  return labels[status] || status
}

// Extract repo name from URL
const getRepoName = (url: string) => {
  const match = url.match(/github\.com\/([^/]+\/[^/]+)/)
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
const handleRetry = async (request: AnalysisRequest) => {
  await analysisStore.retryRequest(request.id)
}

const handleCancel = async (request: AnalysisRequest) => {
  if (confirm('Are you sure you want to cancel this analysis?')) {
    await analysisStore.cancelRequest(request.id)
  }
}

const handleDelete = async (request: AnalysisRequest) => {
  if (confirm('Are you sure you want to delete this request?')) {
    await analysisStore.deleteRequest(request.id)
  }
}

// Re-fetch completed analysis (re-collect from GitHub)
const handleRefetch = async (request: AnalysisRequest) => {
  if (confirm('Do you want to re-fetch content from GitHub? The existing analysis results will be replaced.')) {
    await analysisStore.retryRequest(request.id)
  }
}

// Edit content generated from analysis
const handleEditContent = async (contentId: string) => {
  // Fetch the content details and open edit modal
  const content = await contentStore.getById(contentId)
  if (content) {
    openEditModal(content)
  } else {
    alert('Failed to load content.')
  }
}

// Publish content from analysis
const handlePublishContent = async (contentId: string) => {
  if (!confirm('Do you want to publish this content?')) return
  
  const result = await contentStore.updateStatus(contentId, 'published')
  if (result) {
    alert('Content has been published.')
    // Refresh the content list
    await contentStore.fetchContent()
  } else {
    alert('Failed to publish: ' + (contentStore.error || 'Unknown error'))
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

// Open edit modal with store content item
const openEditModal = (item: StoreContentItem) => {
  editingItem.value = { ...item }
  isEditModalOpen.value = true
}

// Sync from analysis request
const isSyncing = ref(false)
const handleSyncFromAnalysis = async () => {
  if (!editingItem.value?.id || !editingItem.value?.analysis_request_id) {
    alert('No linked analysis request found.')
    return
  }
  
  isSyncing.value = true
  
  try {
    const result = await contentStore.syncFromAnalysis(editingItem.value.id)
    
    if (result) {
      // Update editing item with synced data
      editingItem.value = { ...result }
      // Refresh content list
      await contentStore.fetchAllContent()
      alert('Synced with original data.')
    } else {
      alert('Failed to sync: ' + (contentStore.error || 'Unknown error'))
    }
  } catch (e) {
    console.error('Failed to sync from analysis:', e)
    alert('Failed to sync.')
  } finally {
    isSyncing.value = false
  }
}

// Save edit via API
const saveEdit = async () => {
  if (!editingItem.value || !editingItem.value.id) {
    isEditModalOpen.value = false
    return
  }
  
  isSaving.value = true
  
  try {
    const result = await contentStore.updateContent(editingItem.value.id, {
      title: editingItem.value.title,
      description: editingItem.value.description,
      categories: editingItem.value.categories,
      level: editingItem.value.level,
      duration_minutes: editingItem.value.duration_minutes,
      thumbnail_url: editingItem.value.thumbnail_url,
      icon: editingItem.value.icon,
      // Bilingual fields
      title_kr: editingItem.value.title_kr,
      description_kr: editingItem.value.description_kr,
      // Resource links - use empty string as fallback to ensure field is sent in JSON
      video_url: editingItem.value.video_url || '',
      docs_url: editingItem.value.docs_url || '',
      pptx_url: editingItem.value.pptx_url || '',
    })
    
    if (result) {
      // Success - close modal
      isEditModalOpen.value = false
      editingItem.value = null
    } else {
      alert('Failed to save changes: ' + (contentStore.error || 'Unknown error'))
    }
  } catch (e) {
    console.error('Failed to save edit:', e)
    alert('Failed to save changes')
  } finally {
    isSaving.value = false
  }
}

// Regenerate AI thumbnail
const handleRegenerateThumbnail = async () => {
  if (!editingItem.value?.id) return
  
  if (!confirm('Do you want to regenerate the thumbnail? AI will generate a new image.')) return
  
  isRegeneratingThumbnail.value = true
  
  try {
    const result = await contentStore.regenerateThumbnail(editingItem.value.id)
    
    if (result) {
      editingItem.value.thumbnail_url = result.thumbnail_url
      alert('Thumbnail has been successfully regenerated.')
    } else {
      alert('Failed to regenerate thumbnail: ' + (contentStore.error || 'Unknown error'))
    }
  } catch (e) {
    console.error('Failed to regenerate thumbnail:', e)
    alert('Failed to regenerate thumbnail.')
  } finally {
    isRegeneratingThumbnail.value = false
  }
}

// Open URL in new tab
const openUrl = (url: string) => {
  window.open(url, '_blank')
}

// Archive content (soft delete)
const handleArchive = async (item: StoreContentItem) => {
  if (!confirm('Do you want to archive this content?')) return
  
  const result = await contentStore.updateStatus(item.id, 'archived')
  if (result) {
    // Refresh the list to show updated status
    await contentStore.fetchAllContent()
  } else {
    alert('Failed to archive: ' + (contentStore.error || 'Unknown error'))
  }
}

// Restore archived content to published
const handleRestore = async (item: StoreContentItem) => {
  if (!confirm('Do you want to republish this content?')) return
  
  const result = await contentStore.updateStatus(item.id, 'published')
  if (result) {
    // Refresh the list to show updated status
    await contentStore.fetchAllContent()
  } else {
    alert('Failed to restore: ' + (contentStore.error || 'Unknown error'))
  }
}

// Permanently delete content and linked analysis request
const handlePermanentDelete = async (item: StoreContentItem) => {
  const confirmMessage = item.analysis_request_id 
    ? 'Do you want to permanently delete this content and all linked analysis requests?\n\n⚠️ This action cannot be undone!'
    : 'Do you want to permanently delete this content?\n\n⚠️ This action cannot be undone!'
  
  if (!confirm(confirmMessage)) return
  
  const result = await contentStore.permanentDelete(item.id)
  if (result) {
    // Refresh the list
    await contentStore.fetchAllContent()
    // Also refresh analysis requests if linked
    if (item.analysis_request_id) {
      await analysisStore.fetchRequests()
    }
  } else {
    alert('Failed to permanently delete: ' + (contentStore.error || 'Unknown error'))
  }
}

// Refresh repository metadata (stars, forks, last_commit_date)
const refreshingRepoId = ref<string | null>(null)
const handleRefreshRepo = async (item: StoreContentItem) => {
  if (!item.source_url) {
    alert('Source URL is missing.')
    return
  }
  
  refreshingRepoId.value = item.id
  
  try {
    const result = await contentStore.refreshRepoMetadata(item.id)
    if (result) {
      // Update the item in the list with new data
      await contentStore.fetchAllContent()
    } else {
      alert('Failed to refresh repository metadata: ' + (contentStore.error || 'Unknown error'))
    }
  } catch (e) {
    console.error('Failed to refresh repo metadata:', e)
    alert('Failed to refresh repository metadata.')
  } finally {
    refreshingRepoId.value = null
  }
}

// Lifecycle
onMounted(() => {
  analysisStore.fetchRequests()
  contentStore.fetchAllContent()  // Fetch all content (all statuses, all contributors)
})

onUnmounted(() => {
  analysisStore.stopAllPolling()
})
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-8">
      <h1 class="font-header text-3xl font-bold text-[var(--text-primary)] mb-2">
        Repos
      </h1>
      <p class="text-[var(--text-secondary)]">
        Collect content from GitHub URLs and manage it on this platform.
      </p>
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
        <span v-if="analysisStore.pendingRequests.length > 0" class="ml-1.5 px-1.5 py-0.5 bg-primary/10 text-primary text-xs rounded-full">
          {{ analysisStore.pendingRequests.length }}
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
      <!-- GitHub URL input form -->
      <div class="card p-6">
        <h2 class="font-header text-lg font-semibold text-[var(--text-primary)] mb-4">
          GitHub Repository URL
        </h2>
        
        <form @submit.prevent="handleUrlSubmit" class="space-y-3">
          <div class="flex gap-3">
            <input
              v-model="githubUrl"
              type="url"
              placeholder="https://github.com/username/repository"
              class="flex-1 px-4 py-2.5 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
              :class="{ 'border-red-500 focus:border-red-500': urlError }"
              :disabled="analysisStore.isSubmitting"
            />
            <button 
              type="submit" 
              class="px-6 py-2.5 bg-primary hover:bg-primary-hover text-white font-header font-semibold rounded-lg transition-colors disabled:opacity-50"
              :disabled="analysisStore.isSubmitting"
            >
              <span v-if="analysisStore.isSubmitting" class="flex items-center gap-2">
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
          <p v-else-if="analysisStore.error" class="text-sm text-red-500">{{ analysisStore.error }}</p>
          <p v-else class="text-sm text-[var(--text-tertiary)]">
            💡 The README.md of the repository will be analyzed to automatically extract content information.
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
      <div v-if="analysisStore.isLoading" class="text-center py-12">
        <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <p class="mt-4 text-[var(--text-secondary)]">Loading analysis requests...</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="analysisStore.isEmpty" class="text-center py-12">
        <svg class="mx-auto h-12 w-12 text-[var(--text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
        </svg>
        <h3 class="mt-4 text-lg font-header font-semibold text-[var(--text-primary)]">No analysis requests yet</h3>
        <p class="mt-2 text-[var(--text-secondary)]">Enter a GitHub repository URL above to start content analysis</p>
      </div>

      <!-- Analysis Requests Table -->
      <div v-else class="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl overflow-hidden">
        <table class="w-full">
          <thead>
            <tr class="bg-[var(--bg-secondary)] border-b border-[var(--border)]">
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Repository</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Status</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Progress</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Requester</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Submitted</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Result</th>
              <th class="px-4 py-3 text-right text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--border)]">
            <template v-for="request in filteredAnalysisRequests" :key="request.id">
            <tr class="hover:bg-[var(--bg-secondary)]/50 transition-colors">
              <!-- Repository -->
              <td class="px-4 py-4">
                <a 
                  :href="request.source_url" 
                  target="_blank" 
                  class="text-sm font-medium text-primary hover:underline flex items-center gap-2"
                >
                  <svg class="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                  </svg>
                  {{ getRepoName(request.source_url) }}
                </a>
              </td>
              
              <!-- Status -->
              <td class="px-4 py-4">
                <span :class="['inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border', getStatusBadgeClass(request.status)]">
                  <span v-if="['pending', 'fetching', 'parsing'].includes(request.status)" class="w-2 h-2 mr-1.5 rounded-full bg-current animate-pulse"></span>
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
              
              <!-- Requester -->
              <td class="px-4 py-4 text-sm text-[var(--text-secondary)]">
                {{ request.user_email || '-' }}
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
                      <p class="font-medium text-[var(--text-primary)] truncate max-w-[180px] group-hover:text-primary transition-colors">{{ request.result.title }}</p>
                      <p class="text-xs text-[var(--text-secondary)]">{{ request.content_ids.length }} content(s) created</p>
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
                      @click="handleRefetch(request)"
                      class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-blue-500 hover:bg-blue-500/10 transition-colors"
                      title="Re-fetch from GitHub"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                      </svg>
                    </button>
                    <button
                      @click="toggleExpand(request.id)"
                      class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-primary hover:bg-primary/10 transition-colors"
                      :title="isExpanded(request.id) ? 'Collapse' : 'View details'"
                    >
                      <svg :class="['w-4 h-4 transition-transform', isExpanded(request.id) ? 'rotate-180' : '']" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                      </svg>
                    </button>
                  </template>
                  <template v-if="request.status === 'failed'">
                    <button
                      @click="toggleExpand(request.id)"
                      class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
                      :title="isExpanded(request.id) ? 'Collapse' : 'View details'"
                    >
                      <svg :class="['w-4 h-4 transition-transform', isExpanded(request.id) ? 'rotate-180' : '']" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                      </svg>
                    </button>
                    <button
                      @click="handleRetry(request)"
                      class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-primary hover:bg-primary/10 transition-colors"
                      title="Retry"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                      </svg>
                    </button>
                  </template>
                  <template v-if="['pending', 'fetching', 'parsing'].includes(request.status)">
                    <button
                      @click="handleCancel(request)"
                      class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-yellow-500 hover:bg-yellow-500/10 transition-colors"
                      title="Cancel"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                      </svg>
                    </button>
                  </template>
                  <button
                    @click="handleDelete(request)"
                    class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
                    title="Delete"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
            
            <!-- Expanded Row - Analysis Result Details -->
            <tr v-if="isExpanded(request.id) && request.status === 'completed' && request.result">
              <td colspan="6" class="px-4 py-0">
                <div class="py-4 px-4 bg-[var(--bg-secondary)] rounded-lg mb-4 border border-[var(--border)]">
                  <!-- Result Header -->
                  <div class="flex items-start justify-between mb-4">
                    <div>
                      <h4 class="font-header font-semibold text-[var(--text-primary)]">{{ request.result.title }}</h4>
                      <p v-if="request.result.description" class="text-sm text-[var(--text-secondary)] mt-1">{{ request.result.description }}</p>
                    </div>
                    <div class="flex gap-2">
                      <span v-if="request.result.level" class="px-2 py-1 bg-primary/10 text-primary text-xs font-medium rounded">
                        {{ request.result.level }}
                      </span>
                      <span v-if="request.result.content_type" class="px-2 py-1 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-xs font-medium rounded">
                        {{ request.result.content_type }}
                      </span>
                      <span v-if="request.result.duration_minutes" class="px-2 py-1 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-xs font-medium rounded">
                        {{ request.result.duration_minutes }} min
                      </span>
                    </div>
                  </div>
                  
                  <!-- Categories & Technologies -->
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div v-if="request.result.categories && request.result.categories.length > 0">
                      <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">Categories</p>
                      <div class="flex flex-wrap gap-1.5">
                        <span 
                          v-for="cat in request.result.categories" 
                          :key="cat"
                          class="px-2 py-1 bg-primary/10 text-primary text-xs rounded"
                        >
                          {{ cat }}
                        </span>
                      </div>
                    </div>
                    <div v-if="request.result.technologies && request.result.technologies.length > 0">
                      <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">Technologies</p>
                      <div class="flex flex-wrap gap-1.5">
                        <span 
                          v-for="tech in request.result.technologies" 
                          :key="tech"
                          class="px-2 py-1 bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-xs rounded"
                        >
                          {{ tech }}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <!-- Learning Objectives -->
                  <div v-if="request.result.learning_objectives && request.result.learning_objectives.length > 0" class="mb-4">
                    <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">Learning Objectives</p>
                    <ul class="list-disc list-inside space-y-1">
                      <li v-for="(objective, idx) in request.result.learning_objectives" :key="idx" class="text-sm text-[var(--text-secondary)]">
                        {{ objective }}
                      </li>
                    </ul>
                  </div>
                  
                  <!-- Prerequisites -->
                  <div v-if="request.result.prerequisites && request.result.prerequisites.length > 0" class="mb-4">
                    <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">Prerequisites</p>
                    <ul class="list-disc list-inside space-y-1">
                      <li v-for="(prereq, idx) in request.result.prerequisites" :key="idx" class="text-sm text-[var(--text-secondary)]">
                        {{ prereq }}
                      </li>
                    </ul>
                  </div>
                  
                  <!-- Generated Contents -->
                  <div v-if="request.content_ids && request.content_ids.length > 0">
                    <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">Generated Content ({{ request.content_ids.length }})</p>
                    <div class="space-y-2">
                      <div
                        v-for="contentId in request.content_ids"
                        :key="contentId"
                        class="flex items-center justify-between p-3 bg-[var(--card-bg)] border border-[var(--border)] rounded-lg"
                      >
                        <router-link
                          :to="`/content/${contentId}`"
                          class="flex items-center gap-1.5 text-sm text-primary hover:underline"
                        >
                          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                          </svg>
                          {{ contentId.slice(0, 8) }}...
                        </router-link>
                        <div class="flex items-center gap-2">
                          <button
                            @click="handleEditContent(contentId)"
                            class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-[var(--text-secondary)] hover:text-primary bg-[var(--bg-secondary)] hover:bg-primary/10 rounded-lg transition-colors"
                            title="Edit content"
                          >
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                            </svg>
                            Edit
                          </button>
                          <button
                            @click="handlePublishContent(contentId)"
                            class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
                            title="Publish content"
                          >
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                            </svg>
                            Publish
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <!-- Action Buttons -->
                  <div class="mt-4 pt-4 border-t border-[var(--border)] flex flex-wrap gap-3">
                    <button
                      @click="handleRefetch(request)"
                      class="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-[var(--text-secondary)] bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-lg transition-colors"
                      title="Re-fetch from GitHub"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                      </svg>
                      Re-fetch
                    </button>
                    <button
                      v-if="request.content_ids && request.content_ids.length > 0"
                      @click="handleEditContent(request.content_ids[0]!)"
                      class="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-primary hover:bg-primary-hover rounded-lg transition-colors"
                      title="Edit content"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                      </svg>
                      Edit
                    </button>
                    <button
                      v-if="request.content_ids && request.content_ids.length > 0"
                      @click="handlePublishContent(request.content_ids[0]!)"
                      class="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
                      title="Publish content"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                      </svg>
                      Publish
                    </button>
                  </div>
                  
                  <!-- Completed At -->
                  <div v-if="request.completed_at" class="mt-4 pt-3 border-t border-[var(--border)]">
                    <p class="text-xs text-[var(--text-tertiary)]">
                      Completed: {{ formatDate(request.completed_at) }}
                    </p>
                  </div>
                </div>
              </td>
            </tr>
            
            <!-- Expanded Row - Failed Request Details -->
            <tr v-if="isExpanded(request.id) && request.status === 'failed'">
              <td colspan="6" class="px-4 py-0">
                <div class="py-4 px-4 bg-red-500/5 rounded-lg mb-4 border border-red-500/20">
                  <div class="flex items-start gap-4">
                    <div class="flex-shrink-0">
                      <svg class="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                      </svg>
                    </div>
                    <div class="flex-1">
                      <h4 class="font-header font-semibold text-red-600 mb-2">Analysis Failed</h4>
                      <p class="text-sm text-[var(--text-secondary)] mb-4">
                        {{ request.error_message || 'An unknown error occurred' }}
                      </p>
                      
                      <!-- Status History -->
                      <div v-if="request.status_history && request.status_history.length > 0" class="mb-4">
                        <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">Status History</p>
                        <div class="space-y-1">
                          <div 
                            v-for="(entry, idx) in request.status_history" 
                            :key="idx"
                            class="flex items-center gap-2 text-xs"
                          >
                            <span class="text-[var(--text-tertiary)]">{{ formatDate(entry.timestamp) }}</span>
                            <span :class="['px-1.5 py-0.5 rounded', entry.status === 'failed' ? 'bg-red-500/10 text-red-500' : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]']">
                              {{ getStatusLabel(entry.status) }}
                            </span>
                            <span v-if="entry.message" class="text-[var(--text-secondary)]">{{ entry.message }}</span>
                          </div>
                        </div>
                      </div>
                      
                      <!-- Retry Actions -->
                      <div class="flex gap-3">
                        <button
                          @click="handleRetry(request)"
                          class="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-semibold rounded-lg transition-colors"
                        >
                          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                          </svg>
                          Retry
                        </button>
                        <button
                          @click="handleDelete(request)"
                          class="inline-flex items-center gap-2 px-4 py-2 bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] text-sm font-semibold rounded-lg border border-[var(--border)] transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Polling indicator -->
      <div v-if="analysisStore.activePollingCount > 0" class="text-center text-sm text-[var(--text-secondary)]">
        <span class="inline-flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
          Monitoring {{ analysisStore.activePollingCount }} request(s)...
        </span>
      </div>
    </div>

    <!-- Content Tab (API-connected) -->
    <div v-if="activeTab === 'content'" class="space-y-6">
      <!-- Search bar and language toggle -->
      <div class="flex items-center justify-between gap-4">
        <div class="relative flex-1 max-w-3xl">
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
            @input="onContentSearch"
            type="text"
            placeholder="Search content..."
            class="w-full pl-11 pr-4 py-3 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
          />
        </div>
        <LanguageToggle />
      </div>

      <!-- Loading State -->
      <div v-if="contentStore.isLoading" class="flex justify-center py-12">
        <div class="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent"></div>
      </div>

      <!-- Empty State -->
      <div v-else-if="contentStore.isEmpty" class="text-center py-12">
        <p class="text-[var(--text-secondary)]">No content registered</p>
      </div>

      <!-- Content card grid -->
      <div v-else class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
        <div
          v-for="item in contentStore.items"
          :key="item.id"
          class="card cursor-pointer hover:-translate-y-1 overflow-hidden flex flex-col"
        >
          <!-- Thumbnail or fallback -->
          <div 
            class="aspect-[3/2] flex items-center justify-center relative overflow-hidden"
            :class="item.thumbnail_url ? '' : 'bg-primary'"
          >
            <!-- Status Badge -->
            <span
              v-if="item.status === 'archived'"
              class="absolute top-2 left-2 px-2 py-1 rounded-md text-xs font-header font-semibold uppercase tracking-wide bg-red-600/90 text-white border border-red-500/50 z-10"
            >
              Archived
            </span>
            <span
              v-else-if="item.status === 'draft'"
              class="absolute top-2 left-2 px-2 py-1 rounded-md text-xs font-header font-semibold uppercase tracking-wide bg-yellow-600/80 text-yellow-100 border border-yellow-500/50 z-10"
            >
              Draft
            </span>
            
            <!-- Stars badge (top right) -->
            <div 
              v-if="item.stars" 
              class="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 bg-black/60 backdrop-blur-sm rounded-md text-white text-xs font-semibold z-10"
            >
              <svg class="w-3.5 h-3.5 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
              </svg>
              {{ formatStars(item.stars) }}
            </div>
            
            <!-- Last commit badge (bottom right) -->
            <div 
              v-if="item.last_commit_date" 
              class="absolute bottom-2 right-2 flex items-center gap-1 px-2 py-1 bg-black/60 backdrop-blur-sm rounded-md text-white text-xs z-10"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              {{ formatLastCommit(item.last_commit_date) }}
            </div>
            
            <!-- Thumbnail Image -->
            <img 
              v-if="item.thumbnail_url" 
              :src="item.thumbnail_url" 
              :alt="getLocalizedText(item.title, item.title_kr)"
              class="w-full h-full object-cover"
              loading="lazy"
            />
            <!-- Fallback: GitHub Icon on blue background -->
            <svg 
              v-else
              class="w-12 h-12 text-white/80"
              fill="currentColor" 
              viewBox="0 0 24 24"
            >
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
          </div>
          
          <div class="p-5 flex flex-col flex-1">
            <div class="flex gap-1.5 flex-wrap mb-3">
              <span
                v-for="cat in (item.categories || []).slice(0, 2)"
                :key="cat"
                class="px-2.5 py-1 rounded-md text-xs font-header font-semibold uppercase tracking-wide border transition-colors cursor-pointer"
                :class="{
                  'tag-azure': cat.toLowerCase().includes('azure'),
                  'tag-m365': cat.toLowerCase().includes('m365') || cat.toLowerCase().includes('microsoft 365') || cat.toLowerCase().includes('power'),
                  'tag-workshop': cat.toLowerCase().includes('kubernetes') || cat.toLowerCase().includes('container') || cat.toLowerCase().includes('workshop'),
                  'tag-tutorial': !cat.toLowerCase().includes('azure') && !cat.toLowerCase().includes('m365') && !cat.toLowerCase().includes('kubernetes')
                }"
              >
                {{ cat }}
              </span>
              <span
                v-if="item.level"
                class="px-2.5 py-1 rounded-md text-xs font-header font-semibold uppercase tracking-wide border bg-blue-500/10 text-blue-600 border-blue-500/20"
              >
                {{ item.level }}
              </span>
            </div>

            <h3 class="font-header font-semibold text-base text-[var(--text-primary)] mb-2 line-clamp-2">
              {{ getLocalizedText(item.title, item.title_kr) }}
            </h3>
            
            <p class="text-sm text-[var(--text-secondary)] leading-relaxed mb-4 line-clamp-5">
              {{ getLocalizedText(item.summary_short || item.description, item.summary_kr || item.description_kr) }}
            </p>

            <div class="flex gap-2 pt-4 mt-auto border-t border-[var(--border)]">
              <!-- Refresh Repo Button -->
              <button
                v-if="item.source_url"
                @click.stop="handleRefreshRepo(item)"
                :disabled="refreshingRepoId === item.id"
                class="p-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] hover:border-[var(--border-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
                title="Refresh repository info (stars, forks, last commit)"
              >
                <svg 
                  class="w-4 h-4"
                  :class="{ 'animate-spin': refreshingRepoId === item.id }"
                  viewBox="0 0 24 24" 
                  fill="none" 
                  stroke="currentColor" 
                  stroke-width="2"
                >
                  <path d="M21 12a9 9 0 11-9-9c2.52 0 4.83 1.04 6.49 2.72" stroke-linecap="round"/>
                  <path d="M21 3v6h-6" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </button>
              <button
                v-if="item.source_url"
                @click.stop="openUrl(item.source_url!)"
                class="flex-1 px-4 py-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center gap-1.5 bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] hover:border-[var(--border-hover)]"
              >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
                <span>GitHub</span>
              </button>
              <!-- Edit Button (always visible) -->
              <button
                @click.stop="openEditModal(item)"
                class="flex-1 px-4 py-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center gap-1.5 bg-primary hover:bg-primary-hover text-white"
                title="Edit"
              >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
                <span>Edit</span>
              </button>
              <!-- Restore Button for Archived Content (right of Edit) -->
              <button
                v-if="item.status === 'archived'"
                @click.stop="handleRestore(item)"
                class="flex-1 px-4 py-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center gap-1.5 bg-green-600 hover:bg-green-700 text-white"
                title="Restore"
              >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
                  <path d="M3 3v5h5"></path>
                </svg>
                <span>Restore</span>
              </button>
              <!-- Permanent Delete Button for Archived Content -->
              <button
                v-if="item.status === 'archived'"
                @click.stop="handlePermanentDelete(item)"
                class="p-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center bg-red-600 hover:bg-red-700 text-white"
                title="Permanently delete (content + analysis request)"
              >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M3 6h18"></path>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  <line x1="10" y1="11" x2="10" y2="17"></line>
                  <line x1="14" y1="11" x2="14" y2="17"></line>
                </svg>
              </button>
              <!-- Archive Button (right of Edit, not for archived items) -->
              <button
                v-if="item.status !== 'archived'"
                @click.stop="handleArchive(item)"
                class="p-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center bg-amber-600 hover:bg-amber-700 text-white"
                title="Archive"
              >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 8v13H3V8"></path>
                  <path d="M1 3h22v5H1z"></path>
                  <path d="M10 12h4"></path>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Load More -->
      <div v-if="contentStore.hasMore && !contentStore.isLoading" class="flex justify-center pt-4">
        <button
          @click="contentStore.loadMore()"
          class="px-6 py-2 text-sm font-header font-medium text-primary hover:bg-primary/10 rounded-lg transition-colors"
        >
          Load more
        </button>
      </div>
    </div>

    <!-- Edit Modal -->
    <Dialog v-model:open="isEditModalOpen">
      <DialogContent class="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle class="text-xl font-header">Edit Content</DialogTitle>
          <DialogDescription>
            Modify the content information
          </DialogDescription>
        </DialogHeader>
        
        <div v-if="editingItem" class="grid gap-6 py-4">
          <!-- EN/KR Language Toggle -->
          <div class="flex items-center justify-between p-3 bg-[var(--bg-secondary)] rounded-lg border border-[var(--border)]">
            <span class="text-sm font-medium text-[var(--text-secondary)]">Edit Language</span>
            <div class="flex items-center gap-2">
              <button
                @click="editLanguage = 'en'"
                :class="[
                  'px-3 py-1.5 text-sm font-medium rounded-md transition-all',
                  editLanguage === 'en' 
                    ? 'bg-primary text-white' 
                    : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                ]"
              >
                EN
              </button>
              <button
                @click="editLanguage = 'ko'"
                :class="[
                  'px-3 py-1.5 text-sm font-medium rounded-md transition-all',
                  editLanguage === 'ko' 
                    ? 'bg-primary text-white' 
                    : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                ]"
              >
                KO
              </button>
            </div>
          </div>

          <!-- Title (EN) -->
          <div v-show="editLanguage === 'en'" class="grid gap-2">
            <Label for="title">Title (English)</Label>
            <Input id="title" v-model="editingItem.title" placeholder="Content Title" />
          </div>

          <!-- Title (KR) -->
          <div v-show="editLanguage === 'ko'" class="grid gap-2">
            <Label for="title_kr">Title (Korean)</Label>
            <Input id="title_kr" v-model="editingItem.title_kr" placeholder="Content Title (Korean)" />
          </div>

          <!-- Description (EN) -->
          <div v-show="editLanguage === 'en'" class="grid gap-2">
            <Label for="description">Description (English)</Label>
            <textarea 
              id="description"
              v-model="editingItem.description"
              class="min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
              placeholder="Enter content description"
            />
          </div>

          <!-- Description (KR) -->
          <div v-show="editLanguage === 'ko'" class="grid gap-2">
            <Label for="description_kr">Description (Korean)</Label>
            <textarea 
              id="description_kr"
              v-model="editingItem.description_kr"
              class="min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
              placeholder="Enter content description (Korean)"
            />
          </div>

          <!-- Categories -->
          <div class="grid gap-2">
            <Label for="categories">Categories (comma separated)</Label>
            <Input 
              id="categories" 
              :value="(editingItem.categories || []).join(', ')"
              @input="editingItem.categories = ($event.target as HTMLInputElement).value.split(',').map((s: string) => s.trim()).filter(Boolean)"
              placeholder="Azure, Kubernetes, Container" 
            />
          </div>

          <div class="grid grid-cols-2 gap-4">
            <!-- Level -->
            <div class="grid gap-2">
              <Label for="level">Level</Label>
              <select 
                id="level"
                v-model="editingItem.level"
                class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </div>

            <!-- Estimated Time -->
            <div class="grid gap-2">
              <Label for="duration">Estimated Time (min)</Label>
              <Input 
                id="duration" 
                type="number" 
                v-model.number="editingItem.duration_minutes"
                placeholder="60"
                min="1"
                max="480"
              />
            </div>
          </div>

          <!-- Thumbnail URL with AI Generation -->
          <div class="grid gap-2">
            <Label for="thumbnail">Thumbnail URL</Label>
            <div class="flex gap-2">
              <Input 
                id="thumbnail" 
                v-model="editingItem.thumbnail_url" 
                type="url" 
                placeholder="https://example.com/image.jpg"
                class="flex-1"
              />
              <button
                @click="handleRegenerateThumbnail"
                :disabled="isRegeneratingThumbnail || isSaving"
                class="px-3 py-2 rounded-lg text-sm font-medium transition-all bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 whitespace-nowrap"
                title="Generate new thumbnail with AI"
              >
                <span v-if="isRegeneratingThumbnail" class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
                <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                {{ isRegeneratingThumbnail ? 'Generating...' : 'AI Generate' }}
              </button>
            </div>
            <p class="text-xs text-[var(--text-tertiary)]">
              AI automatically generates a professional Microsoft-style thumbnail based on the workshop content.
            </p>
          </div>

          <!-- Thumbnail Preview -->
          <div v-if="editingItem.thumbnail_url" class="grid gap-2">
            <Label>Thumbnail Preview</Label>
            <div class="relative aspect-[3/2] w-full max-w-md rounded-lg overflow-hidden border border-[var(--border)] bg-[var(--bg-secondary)]">
              <img 
                :src="editingItem.thumbnail_url" 
                :alt="editingItem.title"
                class="w-full h-full object-cover"
                @error="(e) => (e.target as HTMLImageElement).style.display = 'none'"
              />
            </div>
          </div>

          <!-- Icon -->
          <div class="grid gap-2">
            <Label for="icon">Icon</Label>
            <Input 
              id="icon" 
              v-model="editingItem.icon" 
              placeholder="📚"
            />
          </div>

          <!-- Resource Links Section -->
          <div class="border-t border-[var(--border)] pt-4">
            <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-4">Related Resource Links</h3>
            
            <!-- YouTube URL -->
            <div class="grid gap-2 mb-4">
              <Label for="video_url" class="flex items-center gap-2">
                <svg class="w-4 h-4 text-red-500" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
                YouTube Link
              </Label>
              <Input 
                id="video_url" 
                v-model="editingItem.video_url" 
                type="url" 
                placeholder="https://www.youtube.com/watch?v=..."
              />
            </div>

            <!-- PDF URL -->
            <div class="grid gap-2 mb-4">
              <Label for="docs_url" class="flex items-center gap-2">
                <svg class="w-4 h-4 text-red-600" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20 2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-8.5 7.5c0 .83-.67 1.5-1.5 1.5H9v2H7.5V7H10c.83 0 1.5.67 1.5 1.5v1zm5 2c0 .83-.67 1.5-1.5 1.5h-2.5V7H15c.83 0 1.5.67 1.5 1.5v3zm4-3H19v1h1.5V11H19v2h-1.5V7h3v1.5zM9 9.5h1v-1H9v1zM4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm10 5.5h1v-3h-1v3z"/>
                </svg>
                PDF Document Link
              </Label>
              <Input 
                id="docs_url" 
                v-model="editingItem.docs_url" 
                type="url" 
                placeholder="https://example.com/document.pdf"
              />
            </div>

            <!-- PPTX URL -->
            <div class="grid gap-2">
              <Label for="pptx_url" class="flex items-center gap-2">
                <svg class="w-4 h-4 text-orange-500" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M6 2c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6H6zm7 7V3.5L18.5 9H13z"/>
                </svg>
                PPTX Document Link
              </Label>
              <Input 
                id="pptx_url" 
                v-model="editingItem.pptx_url" 
                type="url" 
                placeholder="https://example.com/presentation.pptx"
              />
            </div>
          </div>
        </div>

        <DialogFooter class="flex justify-between gap-2">
          <!-- Left: Sync button -->
          <div class="flex">
            <button 
              @click="handleSyncFromAnalysis"
              :disabled="isSaving || isSyncing || !editingItem?.analysis_request_id"
              class="px-4 py-2.5 rounded-lg text-sm font-header font-semibold transition-all bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              :title="editingItem?.analysis_request_id ? 'Sync with original analysis data' : 'No linked analysis request'"
            >
              <span v-if="isSyncing" class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
              <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {{ isSyncing ? 'Syncing...' : 'Sync' }}
            </button>
          </div>
          
          <!-- Right: Cancel/Save buttons -->
          <div class="flex gap-2">
            <button 
              @click="isEditModalOpen = false"
              :disabled="isSaving"
              class="px-4 py-2.5 rounded-lg text-sm font-header font-semibold transition-all bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] hover:border-[var(--border-hover)] disabled:opacity-50"
            >
              Cancel
            </button>
            <button 
              @click="saveEdit"
              :disabled="isSaving"
              class="px-4 py-2.5 rounded-lg text-sm font-header font-semibold transition-all bg-primary hover:bg-primary-hover text-white disabled:opacity-50 flex items-center gap-2"
            >
              <span v-if="isSaving" class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
              {{ isSaving ? 'Saving...' : 'Save' }}
            </button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>