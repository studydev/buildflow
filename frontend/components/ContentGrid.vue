<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useContentStore } from '@/stores/content'

const contentStore = useContentStore()

// Fetch content on mount
onMounted(async () => {
  if (contentStore.items.length === 0) {
    await contentStore.fetchContent()
  }
})

// Map content items to display format with language support
const displayItems = computed(() => {
  // Access displayLanguage directly to ensure reactivity tracking
  const lang = contentStore.displayLanguage
  
  // Helper to get localized text
  // title = English, title_kr = Korean
  const getLocalizedText = (
    enText: string | undefined, 
    krText: string | undefined,
    fallback: string = ''
  ): string => {
    if (lang === 'ko') {
      return krText || enText || fallback
    }
    return enText || krText || fallback
  }
  
  return contentStore.items.map(item => ({
    id: item.id,
    icon: item.icon || '📄',
    title: getLocalizedText(item.title, item.title_kr),
    description: getLocalizedText(
      item.summary_short || item.description, 
      item.summary_kr || item.description_kr
    ),
    tags: item.categories.slice(0, 3).map((cat, i) => ({
      label: cat,
      color: i === 0 ? 'azure' : i === 1 ? 'workshop' : 'tutorial'
    })),
    actions: [
      { label: 'PDF', icon: 'pdf', primary: false },
      { label: 'YouTube', icon: 'youtube', primary: false },
      { label: 'GitHub', icon: 'github', primary: true, url: item.source_url }
    ],
    level: item.level || item.difficulty_level,
    duration: item.duration_minutes,
    viewCount: item.view_count,
    thumbnailUrl: item.thumbnail_url,
    // Additional localized fields
    prerequisites: lang === 'ko' && item.prerequisites_kr?.length 
      ? item.prerequisites_kr 
      : item.prerequisites,
    learningOutcomes: lang === 'ko' && item.learning_outcomes_kr?.length 
      ? item.learning_outcomes_kr 
      : item.learning_outcomes,
  }))
})

// Fallback to hardcoded data if API fails or for development
const fallbackContentItems = [
  {
    id: '1',
    icon: '🤖',
    title: 'LAB510: VS Code에서 GitHub Copilot의 강력한 기능',
    description: '이 실습형 랩에서는 Visual Studio Code에서 GitHub Copilot을 활용하여 일상적인 코딩 작업에서 가치를 극대화하는 방법을 심층적으로 다룹니다.',
    tags: [
      { label: 'AI', color: 'workshop' },
      { label: 'Copilot', color: 'workshop' },
      { label: 'DevOps', color: 'tutorial' }
    ],
    actions: [
      { label: 'PDF', icon: 'pdf', primary: false },
      { label: 'YouTube', icon: 'youtube', primary: false },
      { label: 'GitHub', icon: 'github', primary: true }
    ]
  },
  {
    id: '2',
    icon: '🔍',
    title: 'LAB511: Azure AI Search로 에이전틱 지식 베이스 구축',
    description: 'Azure AI Search의 차세대 검색 방식인 에이전틱 RAG를 사용하여 Knowledge Base를 구축합니다.',
    tags: [
      { label: 'AI', color: 'workshop' },
      { label: 'Azure', color: 'azure' },
      { label: 'Data', color: 'tutorial' }
    ],
    actions: [
      { label: 'PDF', icon: 'pdf', primary: false },
      { label: 'YouTube', icon: 'youtube', primary: false },
      { label: 'GitHub', icon: 'github', primary: true }
    ]
  },
  {
    id: '3',
    icon: '🎨',
    title: 'LAB512: Microsoft Foundry 및 AI Toolkit을 사용한 멀티모달 에이전트 프로토타이핑',
    description: '이 실습에서는 VS Code에서 AI Toolkit(AITK)과 Microsoft Foundry를 직접 사용하여 Model Catalog의 최신 멀티모달 및 추론 모델을 탐색합니다.',
    tags: [
      { label: 'AI', color: 'workshop' },
      { label: 'Azure', color: 'azure' },
      { label: 'Agent', color: 'workshop' }
    ],
    actions: [
      { label: 'PDF', icon: 'pdf', primary: false },
      { label: 'YouTube', icon: 'youtube', primary: false },
      { label: 'GitHub', icon: 'github', primary: true }
    ]
  },
  {
    id: '4',
    icon: '⚡',
    title: 'LAB514: MCP 및 Azure Functions로 AI 에이전트를 빌드하고 배포하기',
    description: 'Azure Functions를 사용하여 GitHub Copilot과 같은 AI 어시스턴트를 위한 MCP 도구를 만드는 방법을 학습합니다.',
    tags: [
      { label: 'AI', color: 'workshop' },
      { label: 'Azure', color: 'azure' },
      { label: 'DevOps', color: 'tutorial' }
    ],
    actions: [
      { label: 'PDF', icon: 'pdf', primary: false },
      { label: 'YouTube', icon: 'youtube', primary: false },
      { label: 'GitHub', icon: 'github', primary: true }
    ]
  }
]

// Use API data if available, otherwise fallback
const contentItems = computed(() => {
  if (contentStore.items.length > 0) {
    return displayItems.value
  }
  return fallbackContentItems
})

// Handle action click (e.g., open GitHub link)
function handleActionClick(action: { label: string; icon: string; primary: boolean; url?: string }) {
  if (action.url) {
    window.open(action.url, '_blank', 'noopener,noreferrer')
  }
}
</script>

<template>
  <!-- Loading State -->
  <div v-if="contentStore.isLoading && contentStore.items.length === 0" class="flex justify-center items-center py-12">
    <div class="flex flex-col items-center gap-4">
      <div class="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
      <span class="text-[var(--text-secondary)]">콘텐츠를 불러오는 중...</span>
    </div>
  </div>
  
  <!-- Error State -->
  <div v-else-if="contentStore.error" class="flex justify-center items-center py-12">
    <div class="text-center">
      <p class="text-red-500 mb-4">{{ contentStore.error }}</p>
      <button 
        @click="contentStore.fetchContent()"
        class="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-hover"
      >
        다시 시도
      </button>
    </div>
  </div>
  
  <!-- Empty State -->
  <div v-else-if="contentStore.isEmpty" class="flex justify-center items-center py-12">
    <div class="text-center">
      <p class="text-[var(--text-secondary)] mb-2">검색 결과가 없습니다</p>
      <button 
        @click="contentStore.clearFilters()"
        class="text-primary hover:underline"
      >
        필터 초기화
      </button>
    </div>
  </div>
  
  <!-- Content Grid -->
  <div v-else class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
    <div
      v-for="item in contentItems"
      :key="item.id"
      class="card cursor-pointer hover:-translate-y-1 overflow-hidden flex flex-col"
    >
      <!-- Thumbnail or fallback -->
      <div 
        class="h-32 flex items-center justify-center relative overflow-hidden"
        :class="item.thumbnailUrl ? '' : 'bg-primary'"
      >
        <!-- Thumbnail Image -->
        <img 
          v-if="item.thumbnailUrl" 
          :src="item.thumbnailUrl" 
          :alt="item.title"
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
            v-for="tag in item.tags"
            :key="tag.label"
            class="px-2.5 py-1 rounded-md text-xs font-header font-semibold uppercase tracking-wide border transition-colors cursor-pointer"
            :class="{
              'tag-azure': tag.color === 'azure',
              'tag-m365': tag.color === 'm365',
              'tag-workshop': tag.color === 'workshop',
              'tag-tutorial': tag.color === 'tutorial'
            }"
          >
            {{ tag.label }}
          </span>
        </div>
        
        <h3 class="font-header font-semibold text-base text-[var(--text-primary)] mb-2 line-clamp-2">
          {{ item.title }}
        </h3>
        
        <p class="text-sm text-[var(--text-secondary)] leading-relaxed mb-4 line-clamp-5">
          {{ item.description }}
        </p>

        <div class="flex gap-2 pt-4 mt-auto border-t border-[var(--border)]">
          <button
            v-for="action in item.actions"
            :key="action.label"
            @click="handleActionClick(action)"
            :class="[
              'flex-1 px-4 py-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center gap-1.5',
              action.primary
                ? 'bg-primary hover:bg-primary-hover text-white'
                : 'bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] hover:border-[var(--border-hover)]'
            ]"
          >
            <!-- GitHub SVG -->
            <svg v-if="action.icon === 'github'" class="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
            </svg>
            <!-- YouTube SVG -->
            <svg v-else-if="action.icon === 'youtube'" class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
            </svg>
            <!-- PDF SVG -->
            <svg v-else-if="action.icon === 'pdf'" class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zM6 20V4h7v5h5v11H6zm2-8.5h2v1h-2v-1zm0 2h2v1h-2v-1zm0 2h2v1h-2v-1zm4-4h4v5h-4v-5z"/>
            </svg>
            
            <span>{{ action.label }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
  
  <!-- Load More Button -->
  <div v-if="contentStore.hasMore && !contentStore.isLoading" class="flex justify-center mt-8">
    <button 
      @click="contentStore.loadMore()"
      class="px-6 py-3 bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-primary)] rounded-lg border border-[var(--border)] hover:border-[var(--border-hover)] font-header font-semibold transition-all"
    >
      더 보기
    </button>
  </div>
  
  <!-- Loading More -->
  <div v-if="contentStore.isLoading && contentStore.items.length > 0" class="flex justify-center mt-8">
    <div class="w-6 h-6 border-3 border-primary border-t-transparent rounded-full animate-spin"></div>
  </div>
</template>
