<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useAnalysisStore } from '@/stores/analysis'
import type { AnalysisRequest } from '@/stores/analysis'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const analysisStore = useAnalysisStore()

// Form state
const githubUrl = ref('')
const urlError = ref('')

// URL validation
const isValidGithubUrl = (url: string): boolean => {
  const githubPattern = /^https?:\/\/(www\.)?github\.com\/[\w-]+\/[\w.-]+\/?$/
  return githubPattern.test(url)
}

// Computed
const recentRequests = computed(() => {
  return analysisStore.requests.slice(0, 10)
})

const handleSubmit = async () => {
  urlError.value = ''
  
  if (!githubUrl.value.trim()) {
    urlError.value = 'URL을 입력해주세요'
    return
  }
  
  if (!isValidGithubUrl(githubUrl.value.trim())) {
    urlError.value = '유효한 GitHub 저장소 URL을 입력해주세요 (예: https://github.com/owner/repo)'
    return
  }
  
  const newRequest = await analysisStore.submitRequest(githubUrl.value.trim())
  
  if (newRequest) {
    githubUrl.value = ''
    // Polling is automatically started in submitRequest
  }
}

const handleRetry = async (request: AnalysisRequest) => {
  await analysisStore.retryRequest(request.id)
}

const getStatusColor = (status: AnalysisRequest['status']) => {
  switch (status) {
    case 'completed':
      return 'text-success bg-success/10'
    case 'fetching':
    case 'parsing':
      return 'text-warning bg-warning/10'
    case 'failed':
      return 'text-error bg-error/10'
    default:
      return 'text-[var(--text-secondary)] bg-[var(--bg-tertiary)]'
  }
}

const getStatusLabel = (status: AnalysisRequest['status']) => {
  switch (status) {
    case 'completed':
      return '완료'
    case 'fetching':
      return '가져오는 중'
    case 'parsing':
      return '분석 중'
    case 'failed':
      return '실패'
    default:
      return '대기중'
  }
}

// Extract repo name from URL
const getRepoName = (url: string) => {
  const match = url.match(/github\.com\/([^/]+\/[^/]+)/)
  return match ? match[1] : url
}

// Format date
const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

// Lifecycle
onMounted(() => {
  analysisStore.fetchRequests()
})

onUnmounted(() => {
  analysisStore.stopAllPolling()
})
</script>

<template>
  <div>
    <div class="mb-8">
      <h1 class="font-header text-3xl font-bold text-[var(--text-primary)] mb-2">
        Create Content
      </h1>
      <p class="text-[var(--text-secondary)]">
        GitHub 저장소 URL을 입력하여 새로운 학습 콘텐츠를 생성하세요
      </p>
    </div>

    <!-- GitHub URL 입력 폼 -->
    <div class="card p-6 mb-8">
      <h2 class="font-header text-lg font-semibold text-[var(--text-primary)] mb-4">
        GitHub Repository URL
      </h2>
      
      <form @submit.prevent="handleSubmit" class="space-y-3">
        <div class="flex gap-3">
          <Input
            v-model="githubUrl"
            type="url"
            placeholder="https://github.com/username/repository"
            class="flex-1"
            :class="{ 'border-red-500 focus:border-red-500': urlError }"
            :disabled="analysisStore.isSubmitting"
          />
          <Button 
            type="submit" 
            class="bg-primary hover:bg-primary-hover"
            :disabled="analysisStore.isSubmitting"
          >
            <span v-if="analysisStore.isSubmitting" class="flex items-center gap-2">
              <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              제출 중...
            </span>
            <span v-else>분석 요청</span>
          </Button>
        </div>
        
        <p v-if="urlError" class="text-sm text-red-500">{{ urlError }}</p>
        <p v-else-if="analysisStore.error" class="text-sm text-red-500">{{ analysisStore.error }}</p>
        <p v-else class="text-sm text-[var(--text-tertiary)]">
          💡 저장소의 README.md를 분석하여 자동으로 콘텐츠 정보를 추출합니다
        </p>
      </form>
    </div>

    <!-- 요청 현황 테이블 -->
    <div class="card overflow-hidden">
      <div class="px-6 py-4 border-b border-[var(--border)] flex items-center justify-between">
        <h2 class="font-header text-lg font-semibold text-[var(--text-primary)]">
          최근 분석 요청
        </h2>
        <router-link 
          to="/contributor/contribute"
          class="text-sm text-primary hover:underline"
        >
          전체 보기 →
        </router-link>
      </div>

      <!-- Loading -->
      <div v-if="analysisStore.isLoading" class="px-6 py-12 text-center">
        <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <p class="mt-4 text-[var(--text-secondary)]">분석 요청을 불러오는 중...</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="recentRequests.length === 0" class="px-6 py-12 text-center">
        <p class="text-[var(--text-tertiary)]">
          아직 분석 요청이 없습니다. GitHub URL을 입력하여 시작하세요.
        </p>
      </div>

      <!-- Table -->
      <div v-else class="overflow-x-auto">
        <table class="w-full">
          <thead class="bg-[var(--bg-tertiary)]">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Repository
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Status
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Progress
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Result
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Date
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Actions
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--border)]">
            <tr 
              v-for="request in recentRequests" 
              :key="request.id"
              class="hover:bg-[var(--bg-secondary)] transition-colors"
            >
              <td class="px-6 py-4">
                <a 
                  :href="request.source_url" 
                  target="_blank"
                  class="text-sm text-primary hover:underline flex items-center gap-1.5"
                >
                  <svg class="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                  </svg>
                  {{ getRepoName(request.source_url) }}
                </a>
              </td>
              <td class="px-6 py-4">
                <span 
                  :class="[
                    'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                    getStatusColor(request.status)
                  ]"
                >
                  <span v-if="['pending', 'fetching', 'parsing'].includes(request.status)" class="w-1.5 h-1.5 mr-1.5 rounded-full bg-current animate-pulse"></span>
                  {{ getStatusLabel(request.status) }}
                </span>
              </td>
              <td class="px-6 py-4">
                <div class="flex items-center gap-2">
                  <div class="flex-1 h-1.5 bg-[var(--bg-tertiary)] rounded-full overflow-hidden max-w-[80px]">
                    <div 
                      class="h-full bg-primary transition-all duration-500"
                      :style="{ width: `${request.progress}%` }"
                    ></div>
                  </div>
                  <span class="text-xs text-[var(--text-secondary)] tabular-nums">{{ request.progress }}%</span>
                </div>
              </td>
              <td class="px-6 py-4">
                <template v-if="request.status === 'completed' && request.result">
                  <span class="text-sm text-[var(--text-primary)] line-clamp-1">
                    {{ request.result.title }}
                  </span>
                </template>
                <template v-else-if="request.status === 'failed'">
                  <span class="text-sm text-red-500 line-clamp-1" :title="request.error_message">
                    {{ request.error_message || '분석 실패' }}
                  </span>
                </template>
                <template v-else>
                  <span class="text-sm text-[var(--text-tertiary)]">-</span>
                </template>
              </td>
              <td class="px-6 py-4">
                <span class="text-sm text-[var(--text-secondary)]">
                  {{ formatDate(request.created_at) }}
                </span>
              </td>
              <td class="px-6 py-4">
                <Button 
                  v-if="request.status === 'failed'"
                  variant="outline"
                  size="sm"
                  @click="handleRetry(request)"
                  class="text-xs"
                >
                  🔄 재시도
                </Button>
                <span v-else-if="['pending', 'fetching', 'parsing'].includes(request.status)" class="text-xs text-[var(--text-tertiary)]">
                  분석 중...
                </span>
                <span v-else class="text-xs text-[var(--text-tertiary)]">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>