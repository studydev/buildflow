/Users/hyounsookim/Library/Application Support/CleanShot/media/media_hggQmXGAdE/CleanShot 2026-02-03 at 12.18.18@2x.png. <script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import LanguageToggle from '@/components/LanguageToggle.vue'
import { useYouTubeStore } from '@/stores/youtube'
import { useContentStore } from '@/stores/content'

const youtubeStore = useYouTubeStore()
const contentStore = useContentStore()

// Search input state
const searchInput = ref('')
let searchTimeout: number | null = null

// Category filter
const selectedCategory = ref<string | null>(null)

// Advanced filters visibility
const showAdvancedFilters = ref(false)

// Script modal state
const showScriptModal = ref(false)
const selectedContent = ref<any>(null)
const scriptData = ref<any>(null)
const isLoadingScript = ref(false)

// Filter states
type SortOption = 'relevance' | 'popular' | 'recent' | 'likes'
type SortOrder = 'asc' | 'desc'

const selectedSortOption = ref<SortOption>('relevance')
const selectedSortOrder = ref<SortOrder>('desc')

// Pagination state
const currentPage = ref(1)
const limit = ref(20)

// Localized text helper
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

// Sort options (YouTube-specific)
const sortOptions = [
  { label: 'Relevance', value: 'relevance' },
  { label: 'Popular', value: 'popular' },
  { label: 'Likes', value: 'likes' },
  { label: 'Recent', value: 'recent' },
]

// Categories
const categories = [
  { label: 'All Content', value: null },
  { label: 'AI', value: 'AI' },
  { label: 'Azure', value: 'Azure' },
  { label: 'DevOps', value: 'DevOps' },
  { label: 'Web', value: 'Web' },
  { label: 'Cloud', value: 'Cloud' },
  { label: 'Machine Learning', value: 'Machine Learning' },
  { label: 'Copilot', value: 'Copilot' },
  { label: 'Agent', value: 'Agent' },
]

// Pagination computed values
const totalPages = computed(() => Math.ceil(youtubeStore.publishedTotal / limit.value) || 1)
const totalItems = computed(() => youtubeStore.publishedTotal)

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

// Active filter count for badge
const activeFilterCount = computed(() => {
  let count = 0
  if (selectedCategory.value) count++
  if (selectedSortOption.value !== 'relevance') count++
  return count
})

// Debounced search
function handleSearchInput(event: Event) {
  const target = event.target as HTMLInputElement
  searchInput.value = target.value
  
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
  
  searchTimeout = window.setTimeout(() => {
    currentPage.value = 1
    executeSearch()
  }, 300)
}

function executeSearch() {
  youtubeStore.fetchPublishedContents({
    page: currentPage.value,
    limit: limit.value,
    search: searchInput.value || undefined,
    category: selectedCategory.value || undefined,
    sort: selectedSortOption.value !== 'relevance' ? selectedSortOption.value : undefined,
    order: selectedSortOrder.value,
  })
}

function selectCategory(category: string | null) {
  selectedCategory.value = category
  currentPage.value = 1
  executeSearch()
}

function selectSort(sortOption: SortOption) {
  selectedSortOption.value = sortOption
  currentPage.value = 1
  executeSearch()
}

function toggleSortOrder() {
  selectedSortOrder.value = selectedSortOrder.value === 'desc' ? 'asc' : 'desc'
  currentPage.value = 1
  executeSearch()
}

function isSelected(category: string | null) {
  return selectedCategory.value === category
}

function clearAllFilters() {
  searchInput.value = ''
  selectedCategory.value = null
  selectedSortOption.value = 'relevance'
  selectedSortOrder.value = 'desc'
  currentPage.value = 1
  executeSearch()
}

function goToPage(page: number) {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    executeSearch()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

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

// Get tag color class
function getTagColor(index: number): string {
  const colors: string[] = ['azure', 'workshop', 'tutorial']
  return colors[index % colors.length] ?? 'azure'
}

// Open YouTube video
function openVideo(url: string) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

// Open script modal
async function openScript(content: any) {
  selectedContent.value = content
  scriptData.value = null
  isLoadingScript.value = true
  showScriptModal.value = true
  
  // Fetch script via analysis_request_id
  if (content.analysis_request_id) {
    try {
      const script = await youtubeStore.getScript(content.analysis_request_id)
      scriptData.value = script
    } catch (e) {
      console.error('Failed to load script:', e)
    }
  }
  isLoadingScript.value = false
}

// Close script modal
function closeScriptModal() {
  showScriptModal.value = false
  selectedContent.value = null
  scriptData.value = null
}

// Get script text based on language
const getScriptText = computed(() => {
  // First try from fetched script data
  if (scriptData.value) {
    const lang = contentStore.displayLanguage
    if (lang === 'ko') {
      return scriptData.value.script_original_kr || scriptData.value.script_original || 'No script available'
    }
    return scriptData.value.script_original || scriptData.value.script_original_kr || 'No script available'
  }
  // Fallback to content (if script was embedded)
  if (!selectedContent.value) return ''
  const lang = contentStore.displayLanguage
  if (lang === 'ko') {
    return selectedContent.value.script_original_kr || selectedContent.value.script_original || 'No script available'
  }
  return selectedContent.value.script_original || selectedContent.value.script_original_kr || 'No script available'
})

// Load data on mount
onMounted(() => {
  youtubeStore.fetchPublishedContents()
})
</script>

<template>
  <div>
    <!-- 검색바 -->
    <div class="mb-6 max-w-4xl">
      <div class="relative">
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
          type="text"
          :value="searchInput"
          @input="handleSearchInput"
          @keydown.enter="executeSearch"
          placeholder="Search YouTube videos..."
          class="w-full pl-11 pr-28 py-3 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
        />
        <!-- Filter toggle button -->
        <button
          @click="showAdvancedFilters = !showAdvancedFilters"
          :class="[
            'absolute right-3.5 top-1/2 -translate-y-1/2 flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
            showAdvancedFilters || activeFilterCount > 0
              ? 'bg-primary/10 text-primary'
              : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-primary'
          ]"
        >
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"/>
          </svg>
          Filters
          <span 
            v-if="activeFilterCount > 0"
            class="ml-1 px-1.5 py-0.5 text-xs bg-primary text-white rounded-full"
          >
            {{ activeFilterCount }}
          </span>
        </button>
        <!-- Loading indicator -->
        <div v-if="youtubeStore.isLoading && searchInput" class="absolute right-24 top-1/2 -translate-y-1/2">
          <div class="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
        </div>
      </div>

      <!-- Advanced Filters Panel -->
      <Transition
        enter-active-class="transition-all duration-200 ease-out"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition-all duration-150 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-2"
      >
        <div 
          v-if="showAdvancedFilters"
          class="mt-4 px-4 py-2.5 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl flex items-center gap-3 flex-wrap"
        >
          <!-- Sort Options -->
          <div class="flex items-center gap-2">
            <button
              v-for="option in sortOptions"
              :key="option.value"
              @click="selectSort(option.value as SortOption)"
              :class="[
                'px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                selectedSortOption === option.value
                  ? 'bg-primary text-white'
                  : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-primary'
              ]"
            >
              {{ option.label }}
            </button>
            <button
              @click="toggleSortOrder"
              class="p-1 rounded-md bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-primary transition-colors"
              :title="selectedSortOrder === 'desc' ? 'Descending' : 'Ascending'"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path v-if="selectedSortOrder === 'desc'" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3"/>
                <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18"/>
              </svg>
            </button>
          </div>

          <!-- Spacer for right alignment -->
          <div class="flex-1"></div>

          <!-- Apply & Reset (right-aligned) -->
          <div class="flex items-center gap-2">
            <button
              @click="clearAllFilters"
              class="text-xs text-[var(--text-tertiary)] hover:text-primary transition-colors"
            >
              Reset
            </button>
            <button
              @click="executeSearch"
              class="px-3 py-1 bg-primary text-white rounded-md text-xs font-medium hover:bg-primary/90 transition-colors"
            >
              Apply
            </button>
          </div>
        </div>
      </Transition>
    </div>

    <div class="mb-8 flex items-center justify-between">
      <div>
        <h1 class="font-header text-3xl font-bold text-[var(--text-primary)] mb-2">
          YouTube Collection
        </h1>
        <p class="text-[var(--text-secondary)]">
          Curated YouTube videos for learning
        </p>
      </div>
      <!-- Language Toggle -->
      <LanguageToggle />
    </div>

    <div class="flex gap-3 mb-6 flex-wrap">
      <button
        v-for="cat in categories"
        :key="cat.label"
        @click="selectCategory(cat.value)"
        :class="[
          'px-4 py-2 rounded-full text-sm font-header font-medium transition-colors',
          isSelected(cat.value)
            ? 'bg-primary text-white'
            : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-primary hover:text-primary'
        ]"
      >
        {{ cat.label }}
      </button>
    </div>

    <!-- Search Results Summary -->
    <div 
      v-if="searchInput || activeFilterCount > 0" 
      class="mb-4 flex items-center gap-2 text-sm text-[var(--text-secondary)]"
    >
      <span v-if="youtubeStore.publishedTotal > 0">
        Found <strong class="text-[var(--text-primary)]">{{ youtubeStore.publishedTotal }}</strong> results
      </span>
      <span v-if="searchInput">
        for "<strong class="text-[var(--text-primary)]">{{ searchInput }}</strong>"
      </span>
    </div>

    <!-- Loading State -->
    <div v-if="youtubeStore.isLoading && youtubeStore.publishedContents.length === 0" class="flex justify-center py-12">
      <div class="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full"></div>
    </div>

    <!-- Empty State -->
    <div v-else-if="youtubeStore.publishedContents.length === 0" class="text-center py-12">
      <svg class="w-16 h-16 mx-auto text-[var(--text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <h3 class="mt-4 text-lg font-medium text-[var(--text-primary)]">No videos found</h3>
      <p class="mt-2 text-sm text-[var(--text-secondary)]">
        {{ searchInput ? 'Try adjusting your search terms' : 'No published YouTube content yet' }}
      </p>
    </div>

    <!-- Video Grid -->
    <div v-else class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
        <div
          v-for="content in youtubeStore.publishedContents"
          :key="content.id"
          class="group card overflow-hidden flex flex-col"
        >
          <!-- Thumbnail (16:9 aspect ratio for YouTube) -->
          <div class="aspect-video flex items-center justify-center relative overflow-hidden">
            <!-- Thumbnail Image -->
            <img
              v-if="content.thumbnail_url"
              :src="content.thumbnail_url"
              :alt="content.title"
              class="w-full h-full object-cover"
              loading="lazy"
            />
            <!-- Fallback: YouTube Icon on red background -->
            <div v-else class="w-full h-full bg-red-500 flex items-center justify-center">
              <svg class="w-12 h-12 text-white/80" fill="currentColor" viewBox="0 0 24 24">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
            </div>
            
            <!-- Play button overlay (removed - no click action on thumbnail) -->
            <div class="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors"></div>
            
            <!-- View count badge (bottom left) -->
            <div 
              v-if="content.view_count" 
              class="absolute bottom-2 left-2 flex items-center gap-1 px-2 py-1 bg-black/60 backdrop-blur-sm rounded-md text-white text-xs"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
              </svg>
              {{ formatViewCount(content.view_count) }} views
            </div>
            
            <!-- Like count badge (top right) -->
            <div 
              v-if="content.like_count" 
              class="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 bg-black/60 backdrop-blur-sm rounded-md text-white text-xs font-semibold"
            >
              <svg class="w-3.5 h-3.5 text-red-400" fill="currentColor" viewBox="0 0 24 24">
                <path d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5"/>
              </svg>
              {{ formatViewCount(content.like_count) }}
            </div>
            
            <!-- Duration badge (bottom right) -->
            <div class="absolute bottom-2 right-2 flex items-center gap-1 px-2 py-1 bg-black/60 backdrop-blur-sm rounded-md text-white text-xs">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              {{ formatDuration(content.duration_seconds) }}
            </div>
          </div>

          <!-- Content -->
          <div class="p-5 flex flex-col flex-1">
            <!-- Category Tags -->
            <div class="flex gap-1.5 flex-wrap mb-3">
              <span
                v-for="(cat, index) in (content.categories || []).slice(0, 3)"
                :key="cat"
                class="px-2.5 py-1 rounded-md text-xs font-header font-semibold uppercase tracking-wide border transition-colors cursor-pointer"
                :class="{
                  'tag-azure': getTagColor(index) === 'azure',
                  'tag-workshop': getTagColor(index) === 'workshop',
                  'tag-tutorial': getTagColor(index) === 'tutorial'
                }"
              >
                {{ cat }}
              </span>
            </div>
            
            <!-- Title -->
            <h3 class="font-header font-semibold text-base text-[var(--text-primary)] mb-2 line-clamp-2 group-hover:text-primary transition-colors">
              {{ getLocalizedText(content.title_en, content.title_kr, content.title) }}
            </h3>
            
            <!-- Channel name (bold for visibility) -->
            <p v-if="content.channel_name" class="text-sm font-semibold text-[var(--text-primary)] mb-2">
              {{ content.channel_name }}
            </p>
            
            <!-- Description -->
            <p class="text-sm text-[var(--text-secondary)] leading-relaxed line-clamp-5 mb-4">
              {{ getLocalizedText(content.description_en, content.description_kr, content.description) }}
            </p>

            <!-- Action Buttons -->
            <div class="flex gap-2 pt-4 mt-auto border-t border-[var(--border)]">
              <!-- Script Button -->
              <button
                @click="openScript(content)"
                class="flex-1 px-4 py-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center gap-1.5 bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] hover:border-[var(--border-hover)]"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                Script
              </button>
              <!-- YouTube Button -->
              <button
                @click="openVideo(content.source_url)"
                class="flex-1 px-4 py-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center gap-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/30 hover:border-red-500/50"
              >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
                YouTube
              </button>
            </div>
          </div>
        </div>
      </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1 && !youtubeStore.isLoading" class="flex flex-col items-center gap-4 mt-8">
      <!-- Page info -->
      <p class="text-sm text-[var(--text-secondary)]">
        Showing {{ (currentPage - 1) * limit + 1 }}-{{ Math.min(currentPage * limit, totalItems) }} of {{ totalItems }} items
      </p>
      
      <!-- Pagination controls -->
      <nav class="flex items-center gap-1">
        <!-- Previous button -->
        <button
          @click="goToPage(currentPage - 1)"
          :disabled="currentPage === 1"
          class="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          aria-label="Previous page"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        
        <!-- Page numbers -->
        <template v-for="(pageNum, index) in visiblePages" :key="index">
          <span 
            v-if="pageNum === '...'" 
            class="px-3 py-2 text-[var(--text-secondary)]"
          >
            ...
          </span>
          <button
            v-else
            @click="goToPage(pageNum as number)"
            :class="[
              'px-3 py-2 rounded-lg border transition-all font-medium min-w-[40px]',
              pageNum === currentPage
                ? 'bg-primary text-white border-primary'
                : 'border-[var(--border)] bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-primary)]'
            ]"
          >
            {{ pageNum }}
          </button>
        </template>
        
        <!-- Next button -->
        <button
          @click="goToPage(currentPage + 1)"
          :disabled="currentPage === totalPages"
          class="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          aria-label="Next page"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </nav>
    </div>
    
    <!-- Loading indicator when changing pages -->
    <div v-if="youtubeStore.isLoading && youtubeStore.publishedContents.length > 0" class="flex justify-center mt-8">
      <div class="w-6 h-6 border-3 border-primary border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- Script Modal -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-opacity duration-200"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-opacity duration-150"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="showScriptModal"
          class="fixed inset-0 z-50 flex items-center justify-center p-4"
        >
          <!-- Backdrop -->
          <div
            class="absolute inset-0 bg-black/60 backdrop-blur-sm"
            @click="closeScriptModal"
          ></div>

          <!-- Modal Content -->
          <div class="relative bg-[var(--card-bg)] rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden border border-[var(--border)]">
            <!-- Header -->
            <div class="flex items-center justify-between p-6 border-b border-[var(--border)]">
              <div class="flex-1 pr-4">
                <h2 class="text-xl font-bold text-[var(--text-primary)] line-clamp-1">
                  {{ selectedContent ? getLocalizedText(selectedContent.title_en, selectedContent.title_kr, selectedContent.title) : '' }}
                </h2>
                <p v-if="selectedContent?.channel_name" class="text-sm text-[var(--text-secondary)] mt-1">
                  {{ selectedContent.channel_name }}
                </p>
              </div>
              
              <!-- Language Toggle in Modal -->
              <LanguageToggle />

              <button
                @click="closeScriptModal"
                class="ml-4 p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>

            <!-- Script Content -->
            <div class="flex-1 overflow-y-auto p-6">
              <!-- Loading State -->
              <div v-if="isLoadingScript" class="flex items-center justify-center py-12">
                <div class="flex flex-col items-center gap-3">
                  <div class="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin"></div>
                  <p class="text-sm text-[var(--text-secondary)]">Loading script...</p>
                </div>
              </div>
              <!-- Script Content -->
              <div v-else-if="getScriptText && getScriptText !== 'No script available'" class="prose prose-sm max-w-none text-[var(--text-primary)]">
                <pre class="whitespace-pre-wrap font-sans text-sm leading-relaxed bg-[var(--bg-secondary)] p-4 rounded-lg border border-[var(--border)]">{{ getScriptText }}</pre>
              </div>
              <!-- No Script Available -->
              <div v-else class="flex flex-col items-center justify-center py-12 text-center">
                <svg class="w-12 h-12 text-[var(--text-tertiary)] mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                <p class="text-[var(--text-secondary)]">No script available for this video</p>
                <p class="text-sm text-[var(--text-tertiary)] mt-1">The transcript may not have been processed yet</p>
              </div>
            </div>

            <!-- Footer -->
            <div class="flex items-center justify-end gap-3 p-6 border-t border-[var(--border)]">
              <button
                @click="selectedContent?.source_url && openVideo(selectedContent.source_url)"
                class="px-4 py-2 rounded-lg text-sm font-medium bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/30 hover:border-red-500/50 transition-colors flex items-center gap-2"
              >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
                Watch on YouTube
              </button>
              <button
                @click="closeScriptModal"
                class="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] border border-[var(--border)] transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
