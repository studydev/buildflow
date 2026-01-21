<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAnalysisStore } from '@/stores/analysis'
import { useContentStore, type ContentItem as StoreContentItem } from '@/stores/content'
import {
  PipelineStatus,
  isActiveStatus,
  getStatusText,
  getStatusColorClass,
  getPipelineTypeText,
  type PipelineRun,
} from '@/types/pipeline'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const route = useRoute()
const router = useRouter()
const analysisStore = useAnalysisStore()
const contentStore = useContentStore()

// Get content ID from route params
const contentId = computed(() => route.params.id as string)

// Content data
const content = ref<StoreContentItem | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)

// Pipeline runs for this content
const pipelineRuns = computed(() => {
  return analysisStore.pipelineRuns.filter(run => run.content_id === contentId.value)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
})

// Selected run for details
const selectedRun = ref<PipelineRun | null>(null)
const isDetailsModalOpen = ref(false)

// Filter state
const typeFilter = ref<string | null>(null)
const statusFilter = ref<string | null>(null)

// Filtered runs
const filteredRuns = computed(() => {
  let runs = pipelineRuns.value
  
  if (typeFilter.value) {
    runs = runs.filter(r => r.pipeline_type === typeFilter.value)
  }
  
  if (statusFilter.value) {
    runs = runs.filter(r => r.status === statusFilter.value)
  }
  
  return runs
})

// Statistics
const stats = computed(() => {
  const runs = pipelineRuns.value
  return {
    total: runs.length,
    completed: runs.filter(r => r.status === PipelineStatus.COMPLETED).length,
    failed: runs.filter(r => r.status === PipelineStatus.FAILED).length,
    active: runs.filter(r => isActiveStatus(r.status)).length,
  }
})

// Format date
const formatDate = (dateString?: string | null) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('ko-KR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// Calculate duration
const calculateDuration = (run: PipelineRun) => {
  if (!run.started_at) return '-'
  const start = new Date(run.started_at)
  const end = run.completed_at ? new Date(run.completed_at) : new Date()
  const durationMs = end.getTime() - start.getTime()
  
  if (durationMs < 1000) return `${durationMs}ms`
  if (durationMs < 60000) return `${Math.round(durationMs / 1000)}초`
  return `${Math.round(durationMs / 60000)}분 ${Math.round((durationMs % 60000) / 1000)}초`
}

// Actions
const handleRetryPipeline = async (runId: string) => {
  await analysisStore.retryPipeline(runId)
}

const handleCancelPipeline = async (runId: string) => {
  if (confirm('정말로 이 파이프라인을 취소하시겠습니까?')) {
    await analysisStore.cancelPipeline(runId)
  }
}

const startNewPipeline = async (pipelineType: 'analysis' | 'enrichment') => {
  await analysisStore.enqueuePipeline({
    content_id: contentId.value,
    pipeline_type: pipelineType,
  })
}

const openDetailsModal = (run: PipelineRun) => {
  selectedRun.value = run
  isDetailsModalOpen.value = true
}

const goBack = () => {
  router.push('/contributor/edit')
}

// Load data
const loadData = async () => {
  isLoading.value = true
  error.value = null
  
  try {
    // Fetch content details
    await contentStore.fetchContent()
    content.value = contentStore.items.find(item => item.id === contentId.value) || null
    
    if (!content.value) {
      error.value = '콘텐츠를 찾을 수 없습니다'
      return
    }
    
    // Fetch pipeline history
    await analysisStore.getPipelineHistory(contentId.value)
  } catch (e) {
    error.value = '데이터를 불러오는 중 오류가 발생했습니다'
    console.error(e)
  } finally {
    isLoading.value = false
  }
}

// Lifecycle
onMounted(() => {
  loadData()
})

onUnmounted(() => {
  analysisStore.stopAllPipelinePolling()
})

// Watch for content ID changes
watch(contentId, () => {
  loadData()
})
</script>

<template>
  <div>
    <!-- Header with back button -->
    <div class="mb-8">
      <button
        @click="goBack"
        class="flex items-center gap-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors mb-4"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
        </svg>
        콘텐츠 목록으로
      </button>
      
      <div class="flex items-start justify-between">
        <div>
          <h1 class="font-header text-3xl font-bold text-[var(--text-primary)] mb-2">
            파이프라인 히스토리
          </h1>
          <p v-if="content" class="text-[var(--text-secondary)]">
            {{ content.title }}
          </p>
        </div>
        
        <!-- Quick Actions -->
        <div class="flex gap-3">
          <button
            @click="startNewPipeline('analysis')"
            class="px-4 py-2.5 rounded-lg text-sm font-header font-semibold bg-primary hover:bg-primary-hover text-white transition-colors flex items-center gap-2"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
            분석 실행
          </button>
          <button
            @click="startNewPipeline('enrichment')"
            class="px-4 py-2.5 rounded-lg text-sm font-header font-semibold bg-purple-600 hover:bg-purple-700 text-white transition-colors flex items-center gap-2"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/>
            </svg>
            보강 실행
          </button>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="text-center py-12">
      <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      <p class="mt-4 text-[var(--text-secondary)]">불러오는 중...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="text-center py-12">
      <svg class="mx-auto h-12 w-12 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <h3 class="mt-4 text-lg font-header font-semibold text-[var(--text-primary)]">{{ error }}</h3>
      <button
        @click="goBack"
        class="mt-4 px-4 py-2 rounded-lg text-sm font-header font-semibold bg-primary hover:bg-primary-hover text-white transition-colors"
      >
        돌아가기
      </button>
    </div>

    <!-- Main Content -->
    <div v-else class="space-y-6">
      <!-- Stats Cards -->
      <div class="grid grid-cols-4 gap-4">
        <div class="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-4">
          <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">전체 실행</p>
          <p class="text-2xl font-bold text-[var(--text-primary)]">{{ stats.total }}</p>
        </div>
        <div class="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-4">
          <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">완료</p>
          <p class="text-2xl font-bold text-green-500">{{ stats.completed }}</p>
        </div>
        <div class="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-4">
          <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">실패</p>
          <p class="text-2xl font-bold text-red-500">{{ stats.failed }}</p>
        </div>
        <div class="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-4">
          <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">진행 중</p>
          <p class="text-2xl font-bold text-blue-500">{{ stats.active }}</p>
        </div>
      </div>

      <!-- Filters -->
      <div class="flex gap-4 items-center">
        <div class="flex gap-2">
          <span class="text-sm text-[var(--text-secondary)]">타입:</span>
          <button
            @click="typeFilter = null"
            :class="[
              'px-3 py-1.5 rounded-lg text-xs font-header font-medium transition-colors',
              typeFilter === null 
                ? 'bg-primary text-white' 
                : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-primary hover:text-primary'
            ]"
          >
            전체
          </button>
          <button
            @click="typeFilter = 'analysis'"
            :class="[
              'px-3 py-1.5 rounded-lg text-xs font-header font-medium transition-colors',
              typeFilter === 'analysis' 
                ? 'bg-primary text-white' 
                : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-primary hover:text-primary'
            ]"
          >
            분석
          </button>
          <button
            @click="typeFilter = 'enrichment'"
            :class="[
              'px-3 py-1.5 rounded-lg text-xs font-header font-medium transition-colors',
              typeFilter === 'enrichment' 
                ? 'bg-purple-600 text-white' 
                : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-purple-600 hover:text-purple-600'
            ]"
          >
            보강
          </button>
        </div>

        <div class="flex gap-2">
          <span class="text-sm text-[var(--text-secondary)]">상태:</span>
          <button
            @click="statusFilter = null"
            :class="[
              'px-3 py-1.5 rounded-lg text-xs font-header font-medium transition-colors',
              statusFilter === null 
                ? 'bg-primary text-white' 
                : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-primary hover:text-primary'
            ]"
          >
            전체
          </button>
          <button
            @click="statusFilter = PipelineStatus.COMPLETED"
            :class="[
              'px-3 py-1.5 rounded-lg text-xs font-header font-medium transition-colors',
              statusFilter === PipelineStatus.COMPLETED 
                ? 'bg-green-500 text-white' 
                : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-green-500 hover:text-green-500'
            ]"
          >
            완료
          </button>
          <button
            @click="statusFilter = PipelineStatus.FAILED"
            :class="[
              'px-3 py-1.5 rounded-lg text-xs font-header font-medium transition-colors',
              statusFilter === PipelineStatus.FAILED 
                ? 'bg-red-500 text-white' 
                : 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-red-500 hover:text-red-500'
            ]"
          >
            실패
          </button>
        </div>
      </div>

      <!-- Empty State -->
      <div v-if="filteredRuns.length === 0" class="text-center py-12 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl">
        <svg class="mx-auto h-12 w-12 text-[var(--text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
        </svg>
        <h3 class="mt-4 text-lg font-header font-semibold text-[var(--text-primary)]">파이프라인 기록이 없습니다</h3>
        <p class="mt-2 text-[var(--text-secondary)]">위의 버튼을 눌러 파이프라인을 실행하세요</p>
      </div>

      <!-- Pipeline Runs Table -->
      <div v-else class="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl overflow-hidden">
        <table class="w-full">
          <thead>
            <tr class="bg-[var(--bg-secondary)] border-b border-[var(--border)]">
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">ID</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">타입</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">상태</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">생성일</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">소요 시간</th>
              <th class="px-4 py-3 text-left text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">재시도</th>
              <th class="px-4 py-3 text-right text-xs font-header font-semibold text-[var(--text-secondary)] uppercase tracking-wider">작업</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--border)]">
            <tr 
              v-for="run in filteredRuns" 
              :key="run.id" 
              class="hover:bg-[var(--bg-secondary)]/50 transition-colors cursor-pointer"
              @click="openDetailsModal(run)"
            >
              <td class="px-4 py-4">
                <span class="text-sm font-mono text-primary">{{ run.id.slice(0, 8) }}...</span>
              </td>
              <td class="px-4 py-4">
                <span :class="[
                  'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border',
                  run.pipeline_type === 'analysis' 
                    ? 'bg-primary/10 text-primary border-primary/20'
                    : 'bg-purple-500/10 text-purple-600 border-purple-500/20'
                ]">
                  {{ getPipelineTypeText(run.pipeline_type) }}
                </span>
              </td>
              <td class="px-4 py-4">
                <span :class="['inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border', getStatusColorClass(run.status)]">
                  <span v-if="isActiveStatus(run.status)" class="w-2 h-2 mr-1.5 rounded-full bg-current animate-pulse"></span>
                  {{ getStatusText(run.status) }}
                </span>
              </td>
              <td class="px-4 py-4 text-sm text-[var(--text-secondary)]">
                {{ formatDate(run.created_at) }}
              </td>
              <td class="px-4 py-4 text-sm text-[var(--text-secondary)]">
                {{ calculateDuration(run) }}
              </td>
              <td class="px-4 py-4 text-sm text-[var(--text-secondary)]">
                {{ run.retry_count || 0 }} / {{ run.max_retries || 3 }}
              </td>
              <td class="px-4 py-4 text-right" @click.stop>
                <div class="flex items-center justify-end gap-2">
                  <button
                    @click="openDetailsModal(run)"
                    class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-primary hover:bg-primary/10 transition-colors"
                    title="상세 보기"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                    </svg>
                  </button>
                  <template v-if="run.status === PipelineStatus.FAILED">
                    <button
                      @click="handleRetryPipeline(run.id)"
                      class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-primary hover:bg-primary/10 transition-colors"
                      title="재시도"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                      </svg>
                    </button>
                  </template>
                  <template v-if="isActiveStatus(run.status)">
                    <button
                      @click="handleCancelPipeline(run.id)"
                      class="p-2 rounded-lg text-[var(--text-secondary)] hover:text-yellow-500 hover:bg-yellow-500/10 transition-colors"
                      title="취소"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                      </svg>
                    </button>
                  </template>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Active Polling Indicator -->
      <div v-if="analysisStore.pipelinePollingCount > 0" class="text-center text-sm text-[var(--text-secondary)]">
        <span class="inline-flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
          {{ analysisStore.pipelinePollingCount }}개 파이프라인 모니터링 중...
        </span>
      </div>
    </div>

    <!-- Run Details Modal -->
    <Dialog v-model:open="isDetailsModalOpen">
      <DialogContent class="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle class="text-xl font-header">파이프라인 상세</DialogTitle>
          <DialogDescription>
            실행 ID: {{ selectedRun?.id }}
          </DialogDescription>
        </DialogHeader>
        
        <div v-if="selectedRun" class="py-4 space-y-6">
          <!-- Status Badge -->
          <div class="flex items-center justify-between">
            <span :class="['inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium border', getStatusColorClass(selectedRun.status)]">
              <span v-if="isActiveStatus(selectedRun.status)" class="w-2.5 h-2.5 mr-2 rounded-full bg-current animate-pulse"></span>
              {{ getStatusText(selectedRun.status) }}
            </span>
            <span :class="[
              'inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium border',
              selectedRun.pipeline_type === 'analysis' 
                ? 'bg-primary/10 text-primary border-primary/20'
                : 'bg-purple-500/10 text-purple-600 border-purple-500/20'
            ]">
              {{ getPipelineTypeText(selectedRun.pipeline_type) }}
            </span>
          </div>

          <!-- Timeline -->
          <div class="grid grid-cols-2 gap-4 p-4 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)]">
            <div>
              <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">생성일</p>
              <p class="text-sm text-[var(--text-primary)]">{{ formatDate(selectedRun.created_at) }}</p>
            </div>
            <div>
              <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">시작일</p>
              <p class="text-sm text-[var(--text-primary)]">{{ formatDate(selectedRun.started_at) }}</p>
            </div>
            <div>
              <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">완료일</p>
              <p class="text-sm text-[var(--text-primary)]">{{ formatDate(selectedRun.completed_at) }}</p>
            </div>
            <div>
              <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1">소요 시간</p>
              <p class="text-sm text-[var(--text-primary)]">{{ calculateDuration(selectedRun) }}</p>
            </div>
          </div>

          <!-- Retry Info -->
          <div class="p-4 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)]">
            <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">재시도 정보</p>
            <div class="flex items-center gap-4">
              <div class="flex-1">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-sm text-[var(--text-secondary)]">진행률</span>
                  <span class="text-sm font-medium text-[var(--text-primary)]">{{ selectedRun.retry_count || 0 }} / {{ selectedRun.max_retries || 3 }}</span>
                </div>
                <div class="h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
                  <div 
                    class="h-full bg-primary transition-all duration-300"
                    :style="{ width: `${((selectedRun.retry_count || 0) / (selectedRun.max_retries || 3)) * 100}%` }"
                  ></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Error Message -->
          <div v-if="selectedRun.error_message" class="p-4 rounded-lg bg-red-500/10 border border-red-500/20">
            <p class="text-xs font-semibold text-red-500 uppercase tracking-wide mb-2">에러 메시지</p>
            <p class="text-sm text-red-600 font-mono break-all">{{ selectedRun.error_message }}</p>
          </div>

          <!-- Idempotency Key -->
          <div v-if="selectedRun.idempotency_key" class="p-4 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)]">
            <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">멱등성 키</p>
            <p class="text-sm text-[var(--text-primary)] font-mono break-all">{{ selectedRun.idempotency_key }}</p>
          </div>

          <!-- Raw Extraction ID -->
          <div v-if="selectedRun.raw_extraction_id" class="p-4 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)]">
            <p class="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-2">원시 데이터 ID</p>
            <p class="text-sm text-[var(--text-primary)] font-mono">{{ selectedRun.raw_extraction_id }}</p>
          </div>
        </div>

        <DialogFooter class="flex gap-2">
          <template v-if="selectedRun?.status === PipelineStatus.FAILED">
            <button 
              @click="handleRetryPipeline(selectedRun.id); isDetailsModalOpen = false"
              class="px-4 py-2.5 rounded-lg text-sm font-header font-semibold transition-all bg-primary hover:bg-primary-hover text-white flex items-center gap-2"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
              재시도
            </button>
          </template>
          <template v-if="selectedRun && isActiveStatus(selectedRun.status)">
            <button 
              @click="handleCancelPipeline(selectedRun.id); isDetailsModalOpen = false"
              class="px-4 py-2.5 rounded-lg text-sm font-header font-semibold transition-all bg-yellow-500 hover:bg-yellow-600 text-white flex items-center gap-2"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
              취소
            </button>
          </template>
          <button 
            @click="isDetailsModalOpen = false"
            class="px-4 py-2.5 rounded-lg text-sm font-header font-semibold transition-all bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] hover:border-[var(--border-hover)]"
          >
            닫기
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
