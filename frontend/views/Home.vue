<script setup lang="ts">
import { ref, computed } from 'vue'
import ContentGrid from '@/components/ContentGrid.vue'
import LanguageToggle from '@/components/LanguageToggle.vue'
import { useContentStore, type SortOption, type SearchMode } from '@/stores/content'
import { useRoute, useRouter } from 'vue-router'

const contentStore = useContentStore()
const route = useRoute()
const router = useRouter()

// Search input state
const searchInput = ref('')
let searchTimeout: number | null = null

// Advanced filters visibility
const showAdvancedFilters = ref(false)

// Filter states synced with store
const selectedSearchMode = computed({
  get: () => contentStore.searchMode,
  set: (val) => { contentStore.searchMode = val }
})

const selectedSortOption = computed({
  get: () => contentStore.sortOption,
  set: (val) => { contentStore.sortOption = val }
})

const selectedSortOrder = computed({
  get: () => contentStore.sortOrder,
  set: (val) => { contentStore.sortOrder = val }
})

const selectedDifficultyLevel = computed({
  get: () => contentStore.selectedDifficulty,
  set: (val) => { contentStore.selectedDifficulty = val }
})

const minStarsFilter = computed({
  get: () => contentStore.minStars,
  set: (val) => { contentStore.minStars = val }
})

// Sort options
const sortOptions = [
  { label: 'Relevance', value: 'relevance' },
  { label: 'Popular', value: 'popularity' },
  { label: 'Stars', value: 'stars' },
  { label: 'Updated', value: 'recent' },
]

// Search modes
const searchModes = [
  { label: 'Hybrid', value: 'hybrid', description: 'Best of both keyword and semantic' },
  { label: 'Keyword', value: 'keyword', description: 'Exact text matching' },
  { label: 'Semantic', value: 'vector', description: 'AI-powered meaning search' },
]

// Debounced search with advanced filters
function handleSearchInput(event: Event) {
  const target = event.target as HTMLInputElement
  searchInput.value = target.value
  
  // Clear previous timeout
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
  
  // Debounce search by 300ms
  searchTimeout = window.setTimeout(() => {
    executeSearch()
  }, 300)
}

function executeSearch() {
  contentStore.advancedSearch({
    q: searchInput.value,
    mode: selectedSearchMode.value,
    categories: contentStore.selectedCategory ? [contentStore.selectedCategory] : undefined,
    technologies: contentStore.selectedTechnologies.length > 0 ? contentStore.selectedTechnologies : undefined,
    difficulty: selectedDifficultyLevel.value || undefined,
    minStars: minStarsFilter.value > 0 ? minStarsFilter.value : undefined,
    sort: selectedSortOption.value,
    limit: contentStore.limit,
    offset: 0,
  })
  
  // Update URL with search params
  updateUrlParams()
}

function updateUrlParams() {
  const params: Record<string, string> = {}
  
  if (searchInput.value) params.q = searchInput.value
  if (selectedSearchMode.value !== 'hybrid') params.mode = selectedSearchMode.value
  if (contentStore.selectedCategory) params.category = contentStore.selectedCategory
  if (contentStore.selectedTechnologies.length > 0) params.tech = contentStore.selectedTechnologies.join(',')
  if (selectedDifficultyLevel.value) params.difficulty = selectedDifficultyLevel.value
  if (minStarsFilter.value > 0) params.minStars = String(minStarsFilter.value)
  if (selectedSortOption.value !== 'relevance') params.sort = selectedSortOption.value
  
  router.replace({ query: params })
}

// Initialize from URL params
function initFromUrl() {
  const q = route.query
  
  if (q.q) searchInput.value = String(q.q)
  if (q.mode) contentStore.searchMode = q.mode as 'hybrid' | 'keyword' | 'vector'
  if (q.category) contentStore.selectedCategory = String(q.category)
  if (q.tech) contentStore.selectedTechnologies = String(q.tech).split(',')
  if (q.difficulty) contentStore.selectedDifficulty = q.difficulty as 'beginner' | 'intermediate' | 'advanced'
  if (q.minStars) contentStore.minStars = Number(q.minStars)
  if (q.sort) contentStore.sortOption = q.sort as SortOption
  
  // If there are search params, show advanced filters and execute search
  if (Object.keys(q).length > 0) {
    showAdvancedFilters.value = true
    executeSearch()
  }
}

// Category filters
const categories = [
  { label: 'All Content', value: null },
  { label: 'Cloud', value: 'Cloud' },
  { label: 'AI', value: 'AI' },
  { label: 'Agent', value: 'Agent' },
  { label: 'Azure', value: 'Azure' },
  { label: 'Copilot', value: 'Copilot' },
  { label: 'Security', value: 'Security' },
  { label: 'Analytics', value: 'Analytics' },
  { label: 'Machine Learning', value: 'Machine Learning' },
  { label: 'Data', value: 'Data' },
  { label: 'Databases', value: 'Databases' },
  { label: 'DevOps', value: 'DevOps' },
]

function selectCategory(category: string | null) {
  contentStore.setCategory(category)
  executeSearch()
}

function isSelected(category: string | null) {
  return contentStore.selectedCategory === category
}

function clearAllFilters() {
  searchInput.value = ''
  contentStore.searchMode = 'hybrid'
  contentStore.sortOption = 'relevance'
  contentStore.selectedTechnologies = []
  contentStore.selectedDifficulty = null
  contentStore.minStars = 0
  contentStore.selectedCategory = null
  router.replace({ query: {} })
  contentStore.fetchContent()
}

// Active filter count for badge
const activeFilterCount = computed(() => {
  let count = 0
  if (contentStore.selectedTechnologies.length > 0) count++
  if (contentStore.selectedDifficulty) count++
  if (contentStore.minStars > 0) count++
  if (contentStore.searchMode !== 'hybrid') count++
  if (contentStore.sortOption !== 'relevance') count++
  return count
})

// Initialize on mount
initFromUrl()
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
          placeholder="Search workshops, tutorials, and resources..."
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
        <div v-if="contentStore.isLoading && searchInput" class="absolute right-24 top-1/2 -translate-y-1/2">
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
          <!-- Search Mode Toggle -->
          <div class="flex items-center gap-1 bg-[var(--bg-secondary)] rounded-lg p-0.5 border border-[var(--border)]">
            <button
              v-for="mode in searchModes"
              :key="mode.value"
              @click="selectedSearchMode = mode.value as SearchMode"
              :class="[
                'px-2.5 py-1 rounded-md text-xs font-semibold transition-all',
                selectedSearchMode === mode.value
                  ? 'bg-primary text-white shadow-sm'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              ]"
              :title="mode.description"
            >
              {{ mode.label }}
            </button>
          </div>

          <!-- Divider -->
          <div class="h-5 w-px bg-[var(--border)]"></div>

          <!-- Sort Options -->
          <div class="flex items-center gap-2">
            <button
              v-for="option in sortOptions"
              :key="option.value"
              @click="selectedSortOption = option.value as SortOption"
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
              @click="selectedSortOrder = selectedSortOrder === 'desc' ? 'asc' : 'desc'"
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
          Recommended Learning Paths
        </h1>
        <p class="text-[var(--text-secondary)]">
          Curated workshops and tutorials to accelerate your technical skills
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
      <span v-if="contentStore.total > 0">
        Found <strong class="text-[var(--text-primary)]">{{ contentStore.total }}</strong> results
      </span>
      <span v-if="searchInput">
        for "<strong class="text-[var(--text-primary)]">{{ searchInput }}</strong>"
      </span>
      <span v-if="contentStore.selectedTechnologies.length > 0" class="flex gap-1">
        in
        <span 
          v-for="tech in contentStore.selectedTechnologies" 
          :key="tech"
          class="px-2 py-0.5 bg-primary/10 text-primary rounded-full text-xs"
        >
          {{ tech }}
        </span>
      </span>
    </div>

    <ContentGrid />
  </div>
</template>