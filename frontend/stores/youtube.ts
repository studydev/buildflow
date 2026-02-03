/**
 * YouTube Store
 * 
 * Manages YouTube analysis request and content state for contributors.
 * Features:
 * - Submit YouTube URL for analysis
 * - Poll status updates
 * - List user's YouTube requests and content
 * - Publish/unpublish content
 * - Handle errors and retries
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiRequest, APIError } from '@/lib/api'

/**
 * YouTube analysis result with extracted metadata
 */
export interface YouTubeAnalysisResult {
  video_id?: string
  video_url?: string
  channel_id?: string
  channel_name?: string
  title?: string
  title_en?: string
  title_kr?: string
  description_en?: string
  description_kr?: string
  thumbnail_url?: string
  view_count: number
  like_count: number
  duration_seconds: number
  upload_date?: string
  script_summary_en?: string
  script_summary_kr?: string
  content_type?: string
  categories: string[]
  technologies: string[]
  level?: string
}

/**
 * YouTube analysis request item
 */
export interface YouTubeAnalysisRequest {
  id: string
  source_url: string
  video_id: string
  status: 'pending' | 'fetching' | 'transcript' | 'parsing' | 'completed' | 'failed'
  progress: number
  error_message?: string
  result?: YouTubeAnalysisResult
  content_ids: string[]
  user_email?: string
  created_at: string
  updated_at: string
  completed_at?: string
}

/**
 * YouTube content item
 */
export interface YouTubeContent {
  id: string
  video_id: string
  analysis_request_id?: string  // For script lookup
  source_url: string
  channel_name?: string
  title: string
  title_en?: string
  title_kr?: string
  description: string
  description_en?: string
  description_kr?: string
  thumbnail_url?: string
  view_count: number
  like_count: number
  duration_seconds: number
  duration_minutes: number
  upload_date?: string
  script_summary_en?: string
  script_summary_kr?: string
  content_type: string
  status: 'draft' | 'published' | 'archived'
  categories: string[]
  technologies: string[]
  level: string
  created_at: string
  updated_at: string
  published_at?: string
}

/**
 * YouTube script response from analysis request
 */
export interface YouTubeScript {
  video_id: string
  title?: string
  title_kr?: string
  script_original?: string
  script_original_kr?: string
  script_language?: string
  chapters: Array<{
    title: string
    start_time: number
    end_time?: number
  }>
}

/**
 * Alias for YouTubeAnalysisRequest (for component compatibility)
 */
export type YouTubeRequest = YouTubeAnalysisRequest

/**
 * API response for YouTube request list
 */
interface YouTubeRequestListResponse {
  items: YouTubeAnalysisRequest[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

/**
 * API response for YouTube content list
 */
interface YouTubeContentListResponse {
  items: YouTubeContent[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

/**
 * Polling configuration
 * YouTube analysis can take 4-5 minutes for 1-hour videos
 * Set longer intervals to reduce server load
 */
const POLLING_INTERVAL = 10000 // 10 seconds (increased from 2s)
const MAX_POLLING_DURATION = 600000 // 10 minutes (increased from 5m)

export const useYouTubeStore = defineStore('youtube', () => {
  // State - Requests
  const requests = ref<YouTubeAnalysisRequest[]>([])
  const requestsTotal = ref(0)
  const requestsPage = ref(1)
  const requestsLimit = ref(20)
  const requestsHasMore = ref(false)
  
  // State - Content
  const contents = ref<YouTubeContent[]>([])
  const contentsTotal = ref(0)
  const contentsPage = ref(1)
  const contentsLimit = ref(20)
  const contentsHasMore = ref(false)
  
  // State - Published Content (for public listing)
  const publishedContents = ref<YouTubeContent[]>([])
  const publishedTotal = ref(0)
  
  // Loading states
  const isLoading = ref(false)
  const isSubmitting = ref(false)
  const error = ref<string | null>(null)
  
  // Polling state
  const pollingRequests = ref<Set<string>>(new Set())
  const pollingTimers = ref<Map<string, number>>(new Map())
  
  // Getters
  const isEmpty = computed(() => requests.value.length === 0 && !isLoading.value)
  
  const pendingRequests = computed(() => 
    requests.value.filter(r => ['pending', 'fetching', 'transcript', 'parsing'].includes(r.status))
  )
  
  const completedRequests = computed(() => 
    requests.value.filter(r => r.status === 'completed')
  )
  
  const failedRequests = computed(() => 
    requests.value.filter(r => r.status === 'failed')
  )
  
  const activePollingCount = computed(() => pollingRequests.value.size)
  
  // Pagination getters for components
  const requestsPagination = computed(() => ({
    page: requestsPage.value,
    limit: requestsLimit.value,
    total: requestsTotal.value,
    hasMore: requestsHasMore.value,
  }))
  
  const contentsPagination = computed(() => ({
    page: contentsPage.value,
    limit: contentsLimit.value,
    total: contentsTotal.value,
    hasMore: contentsHasMore.value,
  }))
  
  // Actions
  
  /**
   * Fetch YouTube analysis requests for current user
   */
  async function fetchRequests(options: {
    page?: number
    limit?: number
    status?: string
    append?: boolean
  } = {}) {
    const pageNum = options.page ?? requestsPage.value
    const limitNum = options.limit ?? requestsLimit.value
    const append = options.append ?? false
    
    isLoading.value = true
    error.value = null
    
    try {
      const params = new URLSearchParams()
      params.set('page', String(pageNum))
      params.set('limit', String(limitNum))
      if (options.status) {
        params.set('status', options.status)
      }
      
      const data = await apiRequest<YouTubeRequestListResponse>(
        `/youtube/requests?${params.toString()}`
      )
      
      if (append) {
        requests.value = [...requests.value, ...data.items]
      } else {
        requests.value = data.items
      }
      
      requestsTotal.value = data.total
      requestsPage.value = data.page
      requestsLimit.value = data.limit
      requestsHasMore.value = data.has_more
      
      // Start polling for active requests
      startPollingForActiveRequests()
      
    } catch (e) {
      if (e instanceof APIError && e.status === 401) {
        console.warn('Authentication required for fetching YouTube requests')
        return
      }
      error.value = e instanceof Error ? e.message : 'Failed to fetch YouTube requests'
      console.error('Failed to fetch YouTube requests:', e)
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Submit a new YouTube analysis request
   */
  async function submitRequest(sourceUrl: string): Promise<YouTubeAnalysisRequest | null> {
    isSubmitting.value = true
    error.value = null
    
    try {
      const newRequest = await apiRequest<YouTubeAnalysisRequest>(
        '/youtube/analyze',
        {
          method: 'POST',
          body: JSON.stringify({ source_url: sourceUrl }),
        }
      )
      
      // Add to the beginning of the list
      requests.value = [newRequest, ...requests.value]
      requestsTotal.value += 1
      
      // Start polling for this request
      startPolling(newRequest.id)
      
      return newRequest
      
    } catch (e) {
      if (e instanceof APIError && e.status === 401) {
        console.warn('Authentication required for submitting YouTube request')
        return null
      }
      if (e instanceof APIError) {
        error.value = e.message
      } else {
        error.value = e instanceof Error ? e.message : 'Failed to submit YouTube request'
      }
      console.error('Failed to submit YouTube request:', e)
      return null
    } finally {
      isSubmitting.value = false
    }
  }
  
  /**
   * Get a single YouTube request by ID
   */
  async function getRequest(id: string): Promise<YouTubeAnalysisRequest | null> {
    try {
      const data = await apiRequest<YouTubeAnalysisRequest>(
        `/youtube/requests/${id}`
      )
      return data
    } catch (e) {
      console.error(`Failed to get YouTube request ${id}:`, e)
      return null
    }
  }
  
  /**
   * Retry a failed YouTube request
   */
  async function retryRequest(id: string): Promise<YouTubeAnalysisRequest | null> {
    try {
      const data = await apiRequest<YouTubeAnalysisRequest>(
        `/youtube/requests/${id}/retry`,
        { method: 'POST' }
      )
      
      // Update local state
      const index = requests.value.findIndex(r => r.id === id)
      if (index !== -1) {
        requests.value[index] = data
      }
      
      // Start polling
      startPolling(id)
      
      return data
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to retry request'
      console.error(`Failed to retry YouTube request ${id}:`, e)
      return null
    }
  }
  
  /**
   * Delete a YouTube request
   */
  async function deleteRequest(id: string): Promise<boolean> {
    try {
      await apiRequest(
        `/youtube/requests/${id}`,
        { method: 'DELETE' }
      )
      
      // Remove from local state
      requests.value = requests.value.filter(r => r.id !== id)
      requestsTotal.value -= 1
      
      // Stop polling
      stopPolling(id)
      
      return true
    } catch (e) {
      console.error(`Failed to delete YouTube request ${id}:`, e)
      return false
    }
  }
  
  /**
   * Fetch YouTube content for current user
   */
  async function fetchMyContents(options: {
    page?: number
    limit?: number
  } = {}) {
    const pageNum = options.page ?? 1
    const limitNum = options.limit ?? 20
    
    isLoading.value = true
    error.value = null
    
    try {
      const params = new URLSearchParams()
      params.set('page', String(pageNum))
      params.set('limit', String(limitNum))
      
      const data = await apiRequest<YouTubeContentListResponse>(
        `/youtube/contents/my?${params.toString()}`
      )
      
      contents.value = data.items
      contentsTotal.value = data.total || data.items.length
      contentsPage.value = pageNum
      contentsLimit.value = limitNum
      
    } catch (e) {
      if (e instanceof APIError && e.status === 401) {
        console.warn('Authentication required for fetching YouTube contents')
        return
      }
      error.value = e instanceof Error ? e.message : 'Failed to fetch YouTube contents'
      console.error('Failed to fetch YouTube contents:', e)
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Fetch published YouTube content (public) using Azure AI Search
   */
  async function fetchPublishedContents(options: {
    page?: number
    limit?: number
    category?: string
    search?: string
    sort?: string
    order?: string
  } = {}) {
    const pageNum = options.page ?? 1
    const limitNum = options.limit ?? 20
    
    isLoading.value = true
    error.value = null
    
    try {
      const params = new URLSearchParams()
      params.set('page', String(pageNum))
      params.set('limit', String(limitNum))
      if (options.category) {
        params.set('category', options.category)
      }
      if (options.search) {
        params.set('q', options.search)
      }
      if (options.sort) {
        params.set('sort', options.sort)
      }
      if (options.order) {
        params.set('order', options.order)
      }
      
      // Use search endpoint for Azure AI Search
      const data = await apiRequest<YouTubeContentListResponse>(
        `/youtube/search?${params.toString()}`
      )
      
      publishedContents.value = data.items
      publishedTotal.value = data.total
      
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch published contents'
      console.error('Failed to fetch published YouTube contents:', e)
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Get a single YouTube content by ID
   */
  async function getContent(id: string): Promise<YouTubeContent | null> {
    try {
      const data = await apiRequest<YouTubeContent>(
        `/youtube/contents/${id}`
      )
      return data
    } catch (e) {
      console.error(`Failed to get YouTube content ${id}:`, e)
      return null
    }
  }
  
  /**
   * Update YouTube content
   */
  async function updateContent(id: string, updates: Partial<YouTubeContent>): Promise<YouTubeContent | null> {
    try {
      const data = await apiRequest<YouTubeContent>(
        `/youtube/contents/${id}`,
        {
          method: 'PATCH',
          body: JSON.stringify(updates),
        }
      )
      
      // Update local state
      const index = contents.value.findIndex(c => c.id === id)
      if (index !== -1) {
        contents.value[index] = data
      }
      
      return data
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to update content'
      console.error(`Failed to update YouTube content ${id}:`, e)
      return null
    }
  }
  
  /**
   * Publish YouTube content
   */
  async function publishContent(id: string): Promise<YouTubeContent | null> {
    try {
      const data = await apiRequest<YouTubeContent>(
        `/youtube/contents/${id}/publish`,
        { method: 'POST' }
      )
      
      // Update local state
      const index = contents.value.findIndex(c => c.id === id)
      if (index !== -1) {
        contents.value[index] = data
      }
      
      return data
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to publish content'
      console.error(`Failed to publish YouTube content ${id}:`, e)
      return null
    }
  }
  
  /**
   * Unpublish YouTube content
   */
  async function unpublishContent(id: string): Promise<YouTubeContent | null> {
    try {
      const data = await apiRequest<YouTubeContent>(
        `/youtube/contents/${id}/unpublish`,
        { method: 'POST' }
      )
      
      // Update local state
      const index = contents.value.findIndex(c => c.id === id)
      if (index !== -1) {
        contents.value[index] = data
      }
      
      return data
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to unpublish content'
      console.error(`Failed to unpublish YouTube content ${id}:`, e)
      return null
    }
  }
  
  /**
   * Delete YouTube content
   */
  async function deleteContent(id: string): Promise<boolean> {
    try {
      await apiRequest(
        `/youtube/contents/${id}`,
        { method: 'DELETE' }
      )
      
      // Remove from local state
      contents.value = contents.value.filter(c => c.id !== id)
      contentsTotal.value -= 1
      
      return true
    } catch (e) {
      console.error(`Failed to delete YouTube content ${id}:`, e)
      return false
    }
  }
  
  /**
   * Fetch YouTube contents (all for contributor)
   * Alias for fetchMyContents with options
   */
  async function fetchContents(options: {
    page?: number
    limit?: number
  } = {}) {
    return fetchMyContents(options)
  }
  
  /**
   * Get content by ID (alias for getContent)
   */
  async function getContentById(id: string): Promise<YouTubeContent | null> {
    return getContent(id)
  }
  
  /**
   * Refresh metadata for an analysis request
   * Updates view_count, like_count, etc. from YouTube API
   */
  async function refreshRequestMetadata(requestId: string): Promise<{
    view_count: number
    like_count: number
    comment_count: number
    duration_seconds: number
    updated_sources: string[]
  } | null> {
    try {
      const data = await apiRequest<{
        video_id: string
        view_count: number
        like_count: number
        comment_count: number
        duration_seconds: number
        updated_sources: string[]
      }>(
        `/youtube/requests/${requestId}/refresh`,
        { method: 'POST' }
      )
      
      // Update local state
      const index = requests.value.findIndex(r => r.id === requestId)
      if (index !== -1 && requests.value[index].result) {
        requests.value[index].result!.view_count = data.view_count
        requests.value[index].result!.like_count = data.like_count
        requests.value[index].result!.duration_seconds = data.duration_seconds
      }
      
      return data
    } catch (e) {
      console.error(`Failed to refresh metadata for request ${requestId}:`, e)
      return null
    }
  }
  
  /**
   * Refresh metadata for a content item
   */
  async function refreshContentMetadata(contentId: string): Promise<{
    view_count: number
    like_count: number
    comment_count: number
    duration_seconds: number
    updated_sources: string[]
  } | null> {
    try {
      const data = await apiRequest<{
        video_id: string
        view_count: number
        like_count: number
        comment_count: number
        duration_seconds: number
        updated_sources: string[]
      }>(
        `/youtube/refresh/${contentId}`,
        { method: 'POST' }
      )
      
      // Update local state
      const index = contents.value.findIndex(c => c.id === contentId)
      if (index !== -1) {
        contents.value[index].view_count = data.view_count
        contents.value[index].like_count = data.like_count
        contents.value[index].duration_seconds = data.duration_seconds
        contents.value[index].duration_minutes = Math.floor(data.duration_seconds / 60)
      }
      
      return data
    } catch (e) {
      console.error(`Failed to refresh metadata for content ${contentId}:`, e)
      return null
    }
  }
  
  // Polling functions
  
  /**
   * Start polling for a specific request
   */
  function startPolling(requestId: string) {
    if (pollingRequests.value.has(requestId)) {
      return // Already polling
    }
    
    pollingRequests.value.add(requestId)
    const startTime = Date.now()
    
    const poll = async () => {
      // Check if we should stop polling
      if (!pollingRequests.value.has(requestId)) {
        return
      }
      
      // Check timeout
      if (Date.now() - startTime > MAX_POLLING_DURATION) {
        stopPolling(requestId)
        return
      }
      
      try {
        const updated = await getRequest(requestId)
        if (updated) {
          // Update local state
          const index = requests.value.findIndex(r => r.id === requestId)
          if (index !== -1) {
            requests.value[index] = updated
          }
          
          // Stop polling if completed or failed
          if (updated.status === 'completed' || updated.status === 'failed') {
            stopPolling(requestId)
            
            // If completed, refresh contents
            if (updated.status === 'completed') {
              await fetchMyContents()
            }
            return
          }
        }
      } catch (e) {
        console.error(`Polling error for ${requestId}:`, e)
      }
      
      // Schedule next poll
      const timerId = window.setTimeout(poll, POLLING_INTERVAL)
      pollingTimers.value.set(requestId, timerId)
    }
    
    // Start polling immediately
    poll()
  }
  
  /**
   * Stop polling for a specific request
   */
  function stopPolling(requestId: string) {
    pollingRequests.value.delete(requestId)
    
    const timerId = pollingTimers.value.get(requestId)
    if (timerId) {
      clearTimeout(timerId)
      pollingTimers.value.delete(requestId)
    }
  }
  
  /**
   * Start polling for all active requests
   */
  function startPollingForActiveRequests() {
    for (const request of pendingRequests.value) {
      startPolling(request.id)
    }
  }
  
  /**
   * Stop all polling
   */
  function stopAllPolling() {
    for (const requestId of pollingRequests.value) {
      stopPolling(requestId)
    }
  }
  
  /**
   * Get YouTube script by analysis request ID
   * This fetches the full transcript/script from the analysis request
   */
  async function getScript(analysisRequestId: string): Promise<YouTubeScript | null> {
    try {
      const data = await apiRequest<YouTubeScript>(
        `/youtube/script/${analysisRequestId}`
      )
      return data
    } catch (e) {
      console.error(`Failed to get YouTube script for ${analysisRequestId}:`, e)
      return null
    }
  }
  
  /**
   * Clear error
   */
  function clearError() {
    error.value = null
  }
  
  /**
   * Reset store state
   */
  function reset() {
    stopAllPolling()
    requests.value = []
    requestsTotal.value = 0
    contents.value = []
    contentsTotal.value = 0
    publishedContents.value = []
    publishedTotal.value = 0
    error.value = null
    isLoading.value = false
    isSubmitting.value = false
  }
  
  return {
    // State - Requests
    requests,
    requestsTotal,
    requestsPage,
    requestsLimit,
    requestsHasMore,
    
    // State - Content
    contents,
    contentsTotal,
    contentsPage,
    contentsLimit,
    contentsHasMore,
    
    // State - Published
    publishedContents,
    publishedTotal,
    
    // Loading states
    isLoading,
    isSubmitting,
    error,
    
    // Getters
    isEmpty,
    pendingRequests,
    completedRequests,
    failedRequests,
    activePollingCount,
    requestsPagination,
    contentsPagination,
    
    // Request actions
    fetchRequests,
    submitRequest,
    getRequest,
    retryRequest,
    deleteRequest,
    
    // Content actions
    fetchMyContents,
    fetchContents,
    fetchPublishedContents,
    getContent,
    getContentById,
    updateContent,
    publishContent,
    unpublishContent,
    deleteContent,
    getScript,  // Script retrieval
    refreshRequestMetadata,  // Refresh metadata for requests
    refreshContentMetadata,  // Refresh metadata for contents
    
    // Polling
    startPolling,
    stopPolling,
    stopAllPolling,
    
    // Utilities
    clearError,
    reset,
  }
})
