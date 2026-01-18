<script setup lang="ts">
import { ref } from 'vue'
import type { RepoRequest } from '@/types/content'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const githubUrl = ref('')
const repoRequests = ref<RepoRequest[]>([
  {
    id: '1',
    repoUrl: 'https://github.com/Azure-Samples/contoso-real-estate',
    repoName: 'contoso-real-estate',
    status: 'completed',
    repoSummary: 'Enterprise-grade reference architecture for building a real estate website',
    regDate: '2024-01-10',
    contributor: 'John Doe',
    requestor: 'user@microsoft.com'
  },
  {
    id: '2',
    repoUrl: 'https://github.com/Azure/azure-sdk-for-js',
    repoName: 'azure-sdk-for-js',
    status: 'processing',
    repoSummary: 'Azure SDK for JavaScript - client libraries',
    regDate: '2024-01-12',
    contributor: 'Jane Smith',
    requestor: 'user@microsoft.com'
  }
])

const handleSubmit = async () => {
  if (!githubUrl.value.trim()) return
  
  const newRequest: RepoRequest = {
    id: Date.now().toString(),
    repoUrl: githubUrl.value,
    repoName: githubUrl.value.split('/').pop() || '',
    status: 'pending',
    repoSummary: 'Analyzing repository...',
    regDate: new Date().toISOString().split('T')[0],
    contributor: 'Current User',
    requestor: 'user@microsoft.com'
  }
  
  repoRequests.value.unshift(newRequest)
  githubUrl.value = ''
  
  // 백엔드 API 호출 시뮬레이션
  setTimeout(() => {
    const index = repoRequests.value.findIndex(r => r.id === newRequest.id)
    if (index !== -1) {
      repoRequests.value[index].status = 'processing'
    }
  }, 1000)
  
  setTimeout(() => {
    const index = repoRequests.value.findIndex(r => r.id === newRequest.id)
    if (index !== -1) {
      repoRequests.value[index].status = 'completed'
      repoRequests.value[index].repoSummary = 'Repository analysis completed successfully'
    }
  }, 3000)
}

const handleReSync = async (id: string) => {
  const request = repoRequests.value.find(r => r.id === id)
  if (request) {
    request.status = 'processing'
    request.repoSummary = 'Re-syncing repository data...'
    
    // 백엔드 API 호출 시뮬레이션
    setTimeout(() => {
      if (request) {
        request.status = 'completed'
        request.repoSummary = 'Repository re-synced successfully'
      }
    }, 2000)
  }
}

const getStatusColor = (status: RepoRequest['status']) => {
  switch (status) {
    case 'completed':
      return 'text-success bg-success/10'
    case 'processing':
      return 'text-warning bg-warning/10'
    case 'failed':
      return 'text-error bg-error/10'
    default:
      return 'text-[var(--text-secondary)] bg-[var(--bg-tertiary)]'
  }
}

const getStatusLabel = (status: RepoRequest['status']) => {
  switch (status) {
    case 'completed':
      return '완료'
    case 'processing':
      return '처리중'
    case 'failed':
      return '실패'
    default:
      return '대기중'
  }
}
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
      
      <form @submit.prevent="handleSubmit" class="flex gap-3">
        <Input
          v-model="githubUrl"
          type="url"
          placeholder="https://github.com/username/repository"
          class="flex-1"
          required
        />
        <Button type="submit" class="bg-primary hover:bg-primary-hover">
          분석 요청
        </Button>
      </form>

      <p class="text-sm text-[var(--text-tertiary)] mt-3">
        💡 저장소의 README.md를 분석하여 자동으로 콘텐츠 정보를 추출합니다
      </p>
    </div>

    <!-- 요청 현황 테이블 -->
    <div class="card overflow-hidden">
      <div class="px-6 py-4 border-b border-[var(--border)]">
        <h2 class="font-header text-lg font-semibold text-[var(--text-primary)]">
          분석 요청 현황
        </h2>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full">
          <thead class="bg-[var(--bg-tertiary)]">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Repo URL
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Repo Name
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Status
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Summary
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Reg Date
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Contributor
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Requestor
              </th>
              <th class="px-6 py-3 text-left text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                Actions
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--border)]">
            <tr 
              v-for="request in repoRequests" 
              :key="request.id"
              class="hover:bg-[var(--bg-secondary)] transition-colors"
            >
              <td class="px-6 py-4">
                <a 
                  :href="request.repoUrl" 
                  target="_blank"
                  class="text-sm text-primary hover:underline flex items-center gap-1"
                >
                  {{ request.repoUrl.substring(0, 40) }}...
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                  </svg>
                </a>
              </td>
              <td class="px-6 py-4">
                <span class="text-sm font-medium text-[var(--text-primary)]">
                  {{ request.repoName }}
                </span>
              </td>
              <td class="px-6 py-4">
                <span 
                  :class="[
                    'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                    getStatusColor(request.status)
                  ]"
                >
                  {{ getStatusLabel(request.status) }}
                </span>
              </td>
              <td class="px-6 py-4">
                <span class="text-sm text-[var(--text-secondary)] line-clamp-2">
                  {{ request.repoSummary }}
                </span>
              </td>
              <td class="px-6 py-4">
                <span class="text-sm text-[var(--text-secondary)]">
                  {{ request.regDate }}
                </span>
              </td>
              <td class="px-6 py-4">
                <span class="text-sm text-[var(--text-secondary)]">
                  {{ request.contributor }}
                </span>
              </td>
              <td class="px-6 py-4">
                <span class="text-sm text-[var(--text-secondary)]">
                  {{ request.requestor }}
                </span>
              </td>
              <td class="px-6 py-4">
                <Button 
                  variant="outline"
                  size="sm"
                  @click="handleReSync(request.id)"
                  :disabled="request.status === 'processing'"
                  class="text-xs"
                >
                  🔄 Re-Sync
                </Button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="repoRequests.length === 0" class="px-6 py-12 text-center">
        <p class="text-[var(--text-tertiary)]">
          아직 분석 요청이 없습니다. GitHub URL을 입력하여 시작하세요.
        </p>
      </div>
    </div>
  </div>
</template>