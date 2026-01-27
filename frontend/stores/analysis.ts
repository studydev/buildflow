/**
 * Analysis Store
 * 
 * Manages analysis request state for contributors.
 * Features:
 * - Submit GitHub URL for analysis
 * - Poll status updates
 * - List user's analysis requests
 * - Handle errors and retries
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiRequest, APIError } from '@/lib/api'

/**
 * Status history entry
 */
export interface StatusHistoryEntry {
  status: string
  timestamp: string
  message?: string
}

/**
 * Analysis result with extracted metadata
 * Extended to support Korean translations and lab modules
 */
export interface AnalysisResult {
  // 기본 정보
  title: string
  title_kr?: string
  description?: string
  description_kr?: string
  topic?: string
  
  // 분류 정보
  content_type?: string
  categories: string[]
  level?: string
  duration_minutes?: number
  
  // 기술 스택
  technologies: string[]
  prerequisites: string[]
  
  // 학습 정보
  learning_objectives: string[]
  lab_modules: string[]
  
  // 메타데이터
  raw_metadata?: Record<string, unknown>
}

/**
 * Analysis request item
 */
export interface AnalysisRequest {
  id: string
  source_url: string
  status: 'pending' | 'fetching' | 'parsing' | 'completed' | 'failed'
  progress: number
  error_message?: string
  result?: AnalysisResult
  content_ids: string[]
  user_email?: string  // Email of the user who created this request
  created_at: string
  updated_at: string
  completed_at?: string
  status_history?: StatusHistoryEntry[]
}

/**
 * API response for analysis request list
 */
interface AnalysisListResponse {
  items: AnalysisRequest[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

/**
 * Polling configuration
 */
const POLLING_INTERVAL = 2000 // 2 seconds
const MAX_POLLING_DURATION = 300000 // 5 minutes

export const useAnalysisStore = defineStore('analysis', () => {
  // State
  const requests = ref<AnalysisRequest[]>([])
  const total = ref(0)
  const page = ref(1)
  const limit = ref(20)
  const hasMore = ref(false)
  const isLoading = ref(false)
  const isSubmitting = ref(false)
  const error = ref<string | null>(null)
  
  // Polling state
  const pollingRequests = ref<Set<string>>(new Set())
  const pollingTimers = ref<Map<string, number>>(new Map())
  
  // Getters
  const isEmpty = computed(() => requests.value.length === 0 && !isLoading.value)
  
  const pendingRequests = computed(() => 
    requests.value.filter(r => ['pending', 'fetching', 'parsing'].includes(r.status))
  )
  
  const completedRequests = computed(() => 
    requests.value.filter(r => r.status === 'completed')
  )
  
  const failedRequests = computed(() => 
    requests.value.filter(r => r.status === 'failed')
  )
  
  const activePollingCount = computed(() => pollingRequests.value.size)
  
  // Actions
  
  /**
   * Fetch analysis requests for current user
   */
  async function fetchRequests(options: {
    page?: number
    limit?: number
    status?: string
    append?: boolean
  } = {}) {
    const pageNum = options.page ?? page.value
    const limitNum = options.limit ?? limit.value
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
      
      const data = await apiRequest<AnalysisListResponse>(
        `/analysis-requests?${params.toString()}`
      )
      
      if (append) {
        requests.value = [...requests.value, ...data.items]
      } else {
        requests.value = data.items
      }
      
      total.value = data.total
      page.value = data.page
      limit.value = data.limit
      hasMore.value = data.has_more
      
      // Start polling for active requests
      startPollingForActiveRequests()
      
    } catch (e) {
      // Don't show auth errors in the analysis store - these are handled by router/auth
      if (e instanceof APIError && e.status === 401) {
        console.warn('Authentication required for fetching analysis requests')
        // Auth errors are handled by the API layer (logout, redirect)
        return
      }
      error.value = e instanceof Error ? e.message : 'Failed to fetch analysis requests'
      console.error('Failed to fetch analysis requests:', e)
    } finally {
      isLoading.value = false
    }
  }
  
  /**
   * Submit a new analysis request
   */
  async function submitRequest(sourceUrl: string): Promise<AnalysisRequest | null> {
    isSubmitting.value = true
    error.value = null
    
    try {
      const newRequest = await apiRequest<AnalysisRequest>(
        '/analysis-requests',
        {
          method: 'POST',
          body: JSON.stringify({ source_url: sourceUrl }),
        }
      )
      
      // Add to the beginning of the list
      requests.value = [newRequest, ...requests.value]
      total.value += 1
      
      // Start polling for this request
      startPolling(newRequest.id)
      
      return newRequest
      
    } catch (e) {
      // Don't show auth errors in the analysis store - these are handled by router/auth
      if (e instanceof APIError && e.status === 401) {
        console.warn('Authentication required for submitting analysis request')
        return null
      }
      if (e instanceof APIError) {
        error.value = e.message
        // Handle duplicate URL case
        if (e.code === 'DUPLICATE_REQUEST') {
          error.value = 'This URL was already submitted recently. Check your existing requests.'
        }
      } else {
        error.value = e instanceof Error ? e.message : 'Failed to submit analysis request'
      }
      console.error('Failed to submit analysis request:', e)
      return null
    } finally {
      isSubmitting.value = false
    }
  }
  
  /**
   * Get a single analysis request by ID
   */
  async function getRequest(id: string): Promise<AnalysisRequest | null> {
    try {
      const data = await apiRequest<AnalysisRequest>(
        `/analysis-requests/${id}`
      )
      
      return data
    } catch (e) {
      console.error(`Failed to get analysis request ${id}:`, e)
      return null
    }
  }
  
  /**
   * Cancel an analysis request
   */
  async function cancelRequest(id: string): Promise<boolean> {
    try {
      await apiRequest<AnalysisRequest>(
        `/analysis-requests/${id}/cancel`,
        { method: 'POST' }
      )
      
      // Update local state
      const index = requests.value.findIndex(r => r.id === id)
      if (index !== -1 && requests.value[index]) {
        requests.value[index].status = 'failed'
        requests.value[index].error_message = 'Cancelled by user'
      }
      
      // Stop polling
      stopPolling(id)
      
      return true
    } catch (e) {
      console.error(`Failed to cancel analysis request ${id}:`, e)
      return false
    }
  }
  
  /**
   * Delete an analysis request
   */
  async function deleteRequest(id: string): Promise<boolean> {
    try {
      await apiRequest(
        `/analysis-requests/${id}`,
        { method: 'DELETE' }
      )
      
      // Remove from local state
      requests.value = requests.value.filter(r => r.id !== id)
      total.value -= 1
      
      // Stop polling
      stopPolling(id)
      
      return true
    } catch (e) {
      console.error(`Failed to delete analysis request ${id}:`, e)
      return false
    }
  }
  
  /**
   * Retry a failed analysis request (re-submit the same URL)
   */
  async function retryRequest(id: string): Promise<AnalysisRequest | null> {
    const request = requests.value.find(r => r.id === id)
    if (!request) {
      error.value = 'Request not found'
      return null
    }
    
    // Delete the failed request first
    await deleteRequest(id)
    
    // Submit a new request with the same URL
    return submitRequest(request.source_url)
  }
  
  // Polling logic
  
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
      // Check if still need to poll
      if (!pollingRequests.value.has(requestId)) {
        return
      }
      
      // Check timeout
      if (Date.now() - startTime > MAX_POLLING_DURATION) {
        console.warn(`Polling timeout for request ${requestId}`)
        stopPolling(requestId)
        return
      }
      
      try {
        const updatedRequest = await getRequest(requestId)
        
        if (updatedRequest) {
          // Update in local state
          const index = requests.value.findIndex(r => r.id === requestId)
          if (index !== -1) {
            requests.value[index] = updatedRequest
          }
          
          // Stop polling if completed or failed
          if (['completed', 'failed'].includes(updatedRequest.status)) {
            stopPolling(requestId)
            return
          }
        }
        
        // Schedule next poll
        const timer = window.setTimeout(poll, POLLING_INTERVAL)
        pollingTimers.value.set(requestId, timer)
        
      } catch (e) {
        console.error(`Polling error for request ${requestId}:`, e)
        // Continue polling despite errors
        const timer = window.setTimeout(poll, POLLING_INTERVAL)
        pollingTimers.value.set(requestId, timer)
      }
    }
    
    // Start first poll
    poll()
  }
  
  /**
   * Stop polling for a specific request
   */
  function stopPolling(requestId: string) {
    pollingRequests.value.delete(requestId)
    
    const timer = pollingTimers.value.get(requestId)
    if (timer) {
      clearTimeout(timer)
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
   * Clear all state
   */
  function $reset() {
    stopAllPolling()
    requests.value = []
    total.value = 0
    page.value = 1
    hasMore.value = false
    isLoading.value = false
    isSubmitting.value = false
    error.value = null
  }

  /**
   * Go to a specific page
   */
  async function goToPage(targetPage: number) {
    if (targetPage < 1 || isLoading.value) return
    const totalPages = Math.ceil(total.value / limit.value)
    if (targetPage > totalPages) return
    
    page.value = targetPage
    await fetchRequests({ page: targetPage, append: false })
  }

  return {
    // State
    requests,
    total,
    page,
    limit,
    hasMore,
    isLoading,
    isSubmitting,
    error,
    
    // Getters
    isEmpty,
    pendingRequests,
    completedRequests,
    failedRequests,
    activePollingCount,
    
    // Actions
    fetchRequests,
    submitRequest,
    getRequest,
    cancelRequest,
    deleteRequest,
    retryRequest,
    goToPage,
    
    // Polling
    startPolling,
    stopPolling,
    stopAllPolling,
    
    // Reset
    $reset,
  }
})
