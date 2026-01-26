/**
 * Content Store
 * 
 * Manages content list state, search, filtering, and pagination.
 * Per tasks.md T406: Updated for new /api/v1/search endpoint.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiRequest } from '@/lib/api'

export interface ContentItem {
  id: string
  title: string
  description: string
  content_type: string
  status?: string  // draft, published, archived
  categories: string[]
  level?: string
  duration_minutes?: number
  thumbnail_url?: string
  icon?: string
  source_url?: string
  view_count: number
  bookmark_count: number
  published_at?: string
  // Enrichment fields
  summary_short?: string
  summary_long?: string
  difficulty_level?: string
  estimated_time?: string
  learning_outcomes?: string[]
  prerequisites?: string[]
  technologies?: string[]
  popularity_score?: number
  stars?: number
  is_maintained?: boolean
  // Localization fields (Milestone 5)
  title_kr?: string
  description_kr?: string
  summary_kr?: string
  prerequisites_kr?: string[]
  learning_outcomes_kr?: string[]
  // Resource links
  youtube_url?: string
  pdf_url?: string
  pptx_url?: string
  // Link to original analysis request
  analysis_request_id?: string
}

export interface ContentListResponse {
  items: ContentItem[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

// New search types for T406
export type SearchMode = 'hybrid' | 'keyword' | 'vector'
export type SortOption = 'relevance' | 'popularity' | 'recent' | 'stars'

export interface SearchParams {
  q: string
  mode?: SearchMode
  categories?: string[]
  technologies?: string[]
  difficulty?: string
  minStars?: number
  sort?: SortOption
  limit?: number
  offset?: number
}

export interface SearchResultItem {
  id: string
  title: string
  description?: string
  summary?: string
  categories: string[]
  technologies: string[]
  difficulty_level?: string
  popularity_score: number
  stars: number
  score: number
}

export interface FacetValue {
  value: string
  count: number
}

export interface SearchResponse {
  items: SearchResultItem[]
  total: number
  facets: {
    categories?: FacetValue[]
    technologies?: FacetValue[]
    difficulty_level?: FacetValue[]
  }
  query: string
  mode: string
  limit: number
  offset: number
}

export const useContentStore = defineStore('content', () => {
  // State
  const items = ref<ContentItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const limit = ref(20)
  const hasMore = ref(false)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const searchQuery = ref('')
  const selectedCategory = ref<string | null>(null)
  
  // New search state for T406
  const searchMode = ref<SearchMode>('hybrid')
  const sortOption = ref<SortOption>('relevance')
  const selectedTechnologies = ref<string[]>([])
  const selectedDifficulty = ref<string | null>(null)
  const minStars = ref<number>(0)
  const facets = ref<SearchResponse['facets']>({})
  const searchResults = ref<SearchResultItem[]>([])
  
  // Language display state for T502 (Milestone 5)
  const displayLanguage = ref<'en' | 'ko'>('ko')
  
  // Getters
  const isEmpty = computed(() => items.value.length === 0 && !isLoading.value)
  
  const filteredItems = computed(() => {
    // For now, filtering is done server-side
    return items.value
  })
  
  // Actions
  async function fetchContent(options: {
    page?: number
    limit?: number
    category?: string | null
    append?: boolean
  } = {}) {
    const pageNum = options.page ?? page.value
    const limitNum = options.limit ?? limit.value
    const category = options.category ?? selectedCategory.value
    const append = options.append ?? false
    
    isLoading.value = true
    error.value = null
    
    try {
      const params = new URLSearchParams()
      params.set('page', String(pageNum))
      params.set('limit', String(limitNum))
      if (category) {
        params.set('category', category)
      }
      
      const data = await apiRequest<ContentListResponse>(
        `/content?${params.toString()}`
      )
      
      if (append) {
        items.value = [...items.value, ...data.items]
      } else {
        items.value = data.items
      }
      
      total.value = data.total
      page.value = data.page
      limit.value = data.limit
      hasMore.value = data.has_more
      
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch content'
      console.error('Failed to fetch content:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Fetch current user's content (all statuses) for contributor page
   */
  async function fetchMyContent(options: {
    page?: number
    limit?: number
    status?: string | null
    append?: boolean
  } = {}) {
    const pageNum = options.page ?? page.value
    const limitNum = options.limit ?? limit.value
    const statusFilter = options.status ?? null
    const append = options.append ?? false
    
    isLoading.value = true
    error.value = null
    
    try {
      const params = new URLSearchParams()
      params.set('page', String(pageNum))
      params.set('limit', String(limitNum))
      if (statusFilter) {
        params.set('status', statusFilter)
      }
      
      const data = await apiRequest<ContentListResponse>(
        `/content/my?${params.toString()}`
      )
      
      if (append) {
        items.value = [...items.value, ...data.items]
      } else {
        items.value = data.items
      }
      
      total.value = data.total
      page.value = data.page
      limit.value = data.limit
      hasMore.value = data.has_more
      
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch my content'
      console.error('Failed to fetch my content:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Fetch all content (all statuses, all contributors) for contributor management page
   */
  async function fetchAllContent(options: {
    page?: number
    limit?: number
    status?: string | null
    append?: boolean
  } = {}) {
    const pageNum = options.page ?? page.value
    const limitNum = options.limit ?? limit.value
    const statusFilter = options.status ?? null
    const append = options.append ?? false
    
    isLoading.value = true
    error.value = null
    
    try {
      const params = new URLSearchParams()
      params.set('page', String(pageNum))
      params.set('limit', String(limitNum))
      if (statusFilter) {
        params.set('status', statusFilter)
      }
      
      const data = await apiRequest<ContentListResponse>(
        `/content/all?${params.toString()}`
      )
      
      if (append) {
        items.value = [...items.value, ...data.items]
      } else {
        items.value = data.items
      }
      
      total.value = data.total
      page.value = data.page
      limit.value = data.limit
      hasMore.value = data.has_more
      
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch all content'
      console.error('Failed to fetch all content:', e)
    } finally {
      isLoading.value = false
    }
  }
  
  async function search(query: string) {
    if (!query.trim()) {
      // Empty query - fetch all content
      searchQuery.value = ''
      searchResults.value = []
      await fetchContent({ page: 1 })
      return
    }
    
    searchQuery.value = query
    isLoading.value = true
    error.value = null
    
    try {
      const params = new URLSearchParams()
      params.set('q', query)
      params.set('mode', searchMode.value)
      params.set('sort', sortOption.value)
      params.set('limit', String(limit.value))
      params.set('offset', '0')
      
      // Add filters
      if (selectedCategory.value) {
        params.append('categories', selectedCategory.value)
      }
      selectedTechnologies.value.forEach(tech => {
        params.append('technologies', tech)
      })
      if (selectedDifficulty.value) {
        params.set('difficulty', selectedDifficulty.value)
      }
      if (minStars.value !== null) {
        params.set('min_stars', String(minStars.value))
      }
      
      // Use new search API (T406)
      const response = await apiRequest<{ data: SearchResponse }>(
        `/search?${params.toString()}`
      )
      
      const data = response.data || response as unknown as SearchResponse
      
      searchResults.value = data.items
      // Convert to ContentItem format for compatibility
      items.value = data.items.map(item => ({
        id: item.id,
        title: item.title,
        description: item.description || '',
        content_type: 'content',
        categories: item.categories,
        level: item.difficulty_level,
        view_count: 0,
        bookmark_count: 0,
      }))
      total.value = data.total
      facets.value = data.facets
      page.value = 1
      hasMore.value = data.items.length === limit.value && data.total > limit.value
      
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to search content'
      console.error('Failed to search content:', e)
    } finally {
      isLoading.value = false
    }
  }
  
  // New advanced search method (T406)
  async function advancedSearch(params: SearchParams) {
    searchQuery.value = params.q
    isLoading.value = true
    error.value = null
    
    try {
      const urlParams = new URLSearchParams()
      urlParams.set('q', params.q)
      urlParams.set('mode', params.mode || searchMode.value)
      urlParams.set('sort', params.sort || sortOption.value)
      urlParams.set('limit', String(params.limit || limit.value))
      urlParams.set('offset', String(params.offset || 0))
      
      // Add filters
      params.categories?.forEach(cat => urlParams.append('categories', cat))
      params.technologies?.forEach(tech => urlParams.append('technologies', tech))
      if (params.difficulty) urlParams.set('difficulty', params.difficulty)
      if (params.minStars !== undefined) urlParams.set('min_stars', String(params.minStars))
      
      const response = await apiRequest<{ data: SearchResponse }>(
        `/search?${urlParams.toString()}`
      )
      
      const data = response.data || response as unknown as SearchResponse
      
      searchResults.value = data.items
      items.value = data.items.map(item => ({
        id: item.id,
        title: item.title,
        description: item.description || '',
        content_type: 'content',
        categories: item.categories,
        level: item.difficulty_level,
        view_count: 0,
        bookmark_count: 0,
      }))
      total.value = data.total
      facets.value = data.facets
      hasMore.value = data.items.length === (params.limit || limit.value)
      
      return data
      
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to search content'
      console.error('Failed to search content:', e)
      throw e
    } finally {
      isLoading.value = false
    }
  }
  
  async function loadMore() {
    if (!hasMore.value || isLoading.value) return
    
    if (searchQuery.value) {
      // Search mode - load more search results
      const params = new URLSearchParams()
      params.set('q', searchQuery.value)
      params.set('page', String(page.value + 1))
      params.set('limit', String(limit.value))
      
      isLoading.value = true
      
      try {
        const data = await apiRequest<ContentListResponse>(
          `/content/search?${params.toString()}`
        )
        
        items.value = [...items.value, ...data.items]
        page.value = data.page
        hasMore.value = data.has_more
        
      } catch (e) {
        error.value = e instanceof Error ? e.message : 'Failed to load more'
      } finally {
        isLoading.value = false
      }
    } else {
      // Normal mode
      await fetchContent({ page: page.value + 1, append: true })
    }
  }
  
  function setCategory(category: string | null) {
    selectedCategory.value = category
    searchQuery.value = ''
    page.value = 1
    fetchContent({ page: 1, category })
  }
  
  function clearFilters() {
    selectedCategory.value = null
    searchQuery.value = ''
    page.value = 1
    fetchContent({ page: 1, category: null })
  }
  
  async function getById(id: string): Promise<ContentItem | null> {
    try {
      const data = await apiRequest<ContentItem>(
        `/content/${id}`
      )
      return data
    } catch (e) {
      console.error('Failed to get content by ID:', e)
      return null
    }
  }
  
  async function updateContent(id: string, updateData: Partial<ContentItem>): Promise<ContentItem | null> {
    isLoading.value = true
    error.value = null
    
    try {
      const updatedItem = await apiRequest<ContentItem>(
        `/content/${id}`,
        {
          method: 'PUT',
          body: JSON.stringify(updateData),
        }
      )
      
      // Update local item
      const index = items.value.findIndex(item => item.id === id)
      if (index !== -1) {
        items.value[index] = updatedItem
      }
      
      return updatedItem
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to update content'
      console.error('Failed to update content:', e)
      return null
    } finally {
      isLoading.value = false
    }
  }
  
  async function updateStatus(id: string, status: 'published' | 'archived'): Promise<ContentItem | null> {
    isLoading.value = true
    error.value = null
    
    try {
      const updatedItem = await apiRequest<ContentItem>(
        `/content/${id}/status`,
        {
          method: 'PATCH',
          body: JSON.stringify({ status }),
        }
      )
      
      // Update local item with new status
      const index = items.value.findIndex(item => item.id === id)
      if (index !== -1) {
        items.value[index] = updatedItem
      }
      
      return updatedItem
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to update status'
      console.error('Failed to update status:', e)
      return null
    } finally {
      isLoading.value = false
    }
  }
  
  async function syncFromAnalysis(id: string): Promise<ContentItem | null> {
    isLoading.value = true
    error.value = null
    
    try {
      const updatedItem = await apiRequest<ContentItem>(
        `/content/${id}/sync-from-analysis`,
        {
          method: 'POST',
        }
      )
      
      // Update local item with synced data
      const index = items.value.findIndex(item => item.id === id)
      if (index !== -1) {
        items.value[index] = updatedItem
      }
      
      return updatedItem
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to sync from analysis'
      console.error('Failed to sync from analysis:', e)
      return null
    } finally {
      isLoading.value = false
    }
  }
  
  async function deleteContent(id: string): Promise<boolean> {
    isLoading.value = true
    error.value = null
    
    try {
      await apiRequest(
        `/content/${id}`,
        {
          method: 'DELETE',
        }
      )
      
      // Remove from local items
      const index = items.value.findIndex(item => item.id === id)
      if (index !== -1) {
        items.value.splice(index, 1)
        total.value--
      }
      
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to delete content'
      console.error('Failed to delete content:', e)
      return false
    } finally {
      isLoading.value = false
    }
  }
  
  async function permanentDelete(id: string): Promise<boolean> {
    isLoading.value = true
    error.value = null
    
    try {
      await apiRequest(
        `/content/${id}/permanent`,
        {
          method: 'DELETE',
        }
      )
      
      // Remove from local items
      const index = items.value.findIndex(item => item.id === id)
      if (index !== -1) {
        items.value.splice(index, 1)
        total.value--
      }
      
      return true
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to permanently delete content'
      console.error('Failed to permanently delete content:', e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function regenerateThumbnail(id: string): Promise<{ thumbnail_url: string } | null> {
    isLoading.value = true
    error.value = null
    
    try {
      const result = await apiRequest<{ content_id: string; thumbnail_url: string; message: string }>(
        `/content/${id}/regenerate-thumbnail`,
        {
          method: 'POST',
        }
      )
      
      if (!result || !result.thumbnail_url) {
        throw new Error('No thumbnail URL in response')
      }
      
      // Update local item with new thumbnail
      const index = items.value.findIndex(item => item.id === id)
      if (index !== -1 && items.value[index]) {
        items.value[index].thumbnail_url = result.thumbnail_url
      }
      
      return { thumbnail_url: result.thumbnail_url }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to regenerate thumbnail'
      console.error('Failed to regenerate thumbnail:', e)
      return null
    } finally {
      isLoading.value = false
    }
  }
  
  function reset() {
    items.value = []
    total.value = 0
    page.value = 1
    hasMore.value = false
    isLoading.value = false
    error.value = null
    searchQuery.value = ''
    selectedCategory.value = null
  }
  
  return {
    // State
    items,
    total,
    page,
    limit,
    hasMore,
    isLoading,
    error,
    searchQuery,
    selectedCategory,
    
    // Search State
    searchMode,
    sortOption,
    selectedTechnologies,
    selectedDifficulty,
    minStars,
    facets,
    searchResults,
    
    // Language State (T502)
    displayLanguage,
    
    // Getters
    isEmpty,
    filteredItems,
    
    // Actions
    fetchContent,
    fetchMyContent,
    fetchAllContent,
    search,
    advancedSearch,
    loadMore,
    setCategory,
    clearFilters,
    getById,
    updateContent,
    updateStatus,
    syncFromAnalysis,
    deleteContent,
    permanentDelete,
    regenerateThumbnail,
    reset,
  }
})
