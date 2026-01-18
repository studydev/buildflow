<script setup lang="ts">
import { ref } from 'vue'
import type { ContentItem } from '@/types/content'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const isEditModalOpen = ref(false)
const editingItem = ref<ContentItem | null>(null)

const contentItems = ref<ContentItem[]>([
  {
    Topic: 'Azure Infrastructure',
    Title: 'Azure Kubernetes Service Deep Dive',
    Title_kr: 'Azure Kubernetes 서비스 심층 분석',
    URL: 'https://github.com/Azure-Samples/aks-workshop',
    Categories: 'Azure, Kubernetes, Container',
    Session_Description: 'Learn to deploy, manage, and scale containerized applications using Azure Kubernetes Service',
    Session_Description_kr: 'Azure Kubernetes Service를 사용하여 컨테이너화된 애플리케이션을 배포, 관리 및 확장하는 방법을 학습합니다',
    Learning_Objectives: 'Understand AKS architecture, Deploy multi-container apps, Implement auto-scaling',
    Lab_Modules: 'Module 1: Setup, Module 2: Deployment, Module 3: Scaling',
    Technologies_Used: 'Azure Kubernetes Service, Docker, Helm',
    Prerequisites: 'Basic Docker knowledge, Azure subscription',
    Contributor: 'John Doe',
    Reg_Date: '2024-01-10',
    Requestor: 'user@microsoft.com',
    Update_Date: '2024-01-15',
    Status: 'completed',
    PPTX_Link: 'https://example.com/deck.pptx',
    PDF_Link: 'https://example.com/deck.pdf',
    Demo_Link: 'https://example.com/demo',
    Youtube_Link: 'https://youtube.com/watch?v=example'
  },
  {
    Topic: 'Microsoft 365',
    Title: 'Power Platform for Business Solutions',
    Title_kr: 'Power Platform 비즈니스 솔루션',
    URL: 'https://github.com/microsoft/PowerPlatform-Samples',
    Categories: 'M365, Power Platform, Low-Code',
    Session_Description: 'Build low-code business applications with Power Apps, automate workflows',
    Session_Description_kr: 'Power Apps로 로우코드 비즈니스 애플리케이션 구축 및 워크플로 자동화',
    Learning_Objectives: 'Create Power Apps, Build Power Automate flows, Analyze with Power BI',
    Lab_Modules: 'Module 1: Power Apps, Module 2: Power Automate, Module 3: Power BI',
    Technologies_Used: 'Power Apps, Power Automate, Power BI',
    Prerequisites: 'Microsoft 365 account, Basic business process knowledge',
    Contributor: 'Jane Smith',
    Reg_Date: '2024-01-12',
    Requestor: 'user@microsoft.com',
    Update_Date: '2024-01-16',
    Status: 'completed',
    PPTX_Link: '',
    PDF_Link: 'https://example.com/m365-deck.pdf',
    Demo_Link: '',
    Youtube_Link: 'https://youtube.com/watch?v=example2'
  }
])

const openEditModal = (item: ContentItem) => {
  editingItem.value = { ...item }
  isEditModalOpen.value = true
}

const saveEdit = () => {
  if (editingItem.value) {
    const index = contentItems.value.findIndex(item => item.URL === editingItem.value!.URL)
    if (index !== -1) {
      contentItems.value[index] = { ...editingItem.value }
      editingItem.value.Update_Date = new Date().toISOString().split('T')[0]
    }
  }
  isEditModalOpen.value = false
}
</script>

<template>
  <div>
    <!-- 검색바 -->
    <div class="mb-8 max-w-3xl">
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
          placeholder="Search contributed content..."
          class="w-full pl-11 pr-4 py-3 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
        />
      </div>
    </div>

    <div class="mb-8">
      <h1 class="font-header text-3xl font-bold text-[var(--text-primary)] mb-2">
        Contribute Content
      </h1>
      <p class="text-[var(--text-secondary)]">
        수집된 학습 콘텐츠를 편집하고 추가 정보를 입력하세요
      </p>
    </div>

    <div class="flex gap-3 mb-6 flex-wrap">
      <button class="px-4 py-2 rounded-full text-sm font-header font-medium bg-primary text-white">
        All Content
      </button>
      <button class="px-4 py-2 rounded-full text-sm font-header font-medium bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-primary hover:text-primary transition-colors">
        Azure
      </button>
      <button class="px-4 py-2 rounded-full text-sm font-header font-medium bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-primary hover:text-primary transition-colors">
        Microsoft 365
      </button>
      <button class="px-4 py-2 rounded-full text-sm font-header font-medium bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-primary hover:text-primary transition-colors">
        Completed
      </button>
      <button class="px-4 py-2 rounded-full text-sm font-header font-medium bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-primary hover:text-primary transition-colors">
        Pending
      </button>
    </div>

    <!-- 콘텐츠 카드 그리드 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
      <div
        v-for="item in contentItems"
        :key="item.URL"
        class="card cursor-pointer hover:-translate-y-1 overflow-hidden flex flex-col"
      >
        <div class="h-48 bg-primary flex items-center justify-center text-white font-header font-bold text-3xl px-6 text-center">
          {{ item.Title_kr || item.Title }}
        </div>
        
        <div class="p-5 flex flex-col flex-1">
          <div class="flex gap-1.5 flex-wrap mb-3">
            <span
              v-for="cat in item.Categories.split(',').slice(0, 2)"
              :key="cat"
              class="px-2.5 py-1 rounded-md text-xs font-header font-semibold uppercase tracking-wide border transition-colors cursor-pointer"
              :class="{
                'tag-azure': cat.trim().toLowerCase().includes('azure'),
                'tag-m365': cat.trim().toLowerCase().includes('m365') || cat.trim().toLowerCase().includes('microsoft 365') || cat.trim().toLowerCase().includes('power'),
                'tag-workshop': cat.trim().toLowerCase().includes('kubernetes') || cat.trim().toLowerCase().includes('container') || cat.trim().toLowerCase().includes('workshop'),
                'tag-tutorial': !cat.trim().toLowerCase().includes('azure') && !cat.trim().toLowerCase().includes('m365') && !cat.trim().toLowerCase().includes('kubernetes')
              }"
            >
              {{ cat.trim() }}
            </span>
            <span
              :class="[
                'px-2.5 py-1 rounded-md text-xs font-header font-semibold uppercase tracking-wide border transition-colors',
                item.Status === 'completed' ? 'bg-success/10 text-success border-success/20' : 'bg-warning/10 text-warning border-warning/20'
              ]"
            >
              {{ item.Status === 'completed' ? '완료' : '처리중' }}
            </span>
          </div>

          <h3 class="font-header font-semibold text-lg text-[var(--text-primary)] mb-2 leading-snug">
            {{ item.Title }}
          </h3>
          
          <p class="text-sm text-[var(--text-secondary)] leading-relaxed mb-4 line-clamp-3">
            {{ item.Session_Description }}
          </p>

          <div class="flex gap-2 pt-4 mt-auto border-t border-[var(--border)]">
            <button
              v-if="item.PDF_Link"
              class="flex-1 px-4 py-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center gap-1.5 bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] hover:border-[var(--border-hover)]"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zM6 20V4h7v5h5v11H6zm2-8.5h2v1h-2v-1zm0 2h2v1h-2v-1zm0 2h2v1h-2v-1zm4-4h4v5h-4v-5z"/>
              </svg>
              <span>PDF</span>
            </button>
            <button
              v-if="item.Youtube_Link"
              class="flex-1 px-4 py-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center gap-1.5 bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] hover:border-[var(--border-hover)]"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
              <span>YouTube</span>
            </button>
            <button
              @click="openEditModal(item)"
              class="flex-1 px-4 py-2.5 rounded-lg text-xs font-header font-semibold transition-all flex items-center justify-center gap-1.5 bg-primary hover:bg-primary-hover text-white"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
              <span>Edit</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 편집 모달 -->
    <Dialog v-model:open="isEditModalOpen">
      <DialogContent class="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle class="text-xl font-header">콘텐츠 편집</DialogTitle>
          <DialogDescription>
            학습 콘텐츠의 정보를 수정하고 추가 자료를 입력하세요
          </DialogDescription>
        </DialogHeader>
        
        <div v-if="editingItem" class="grid gap-6 py-4">
          <!-- 기본 정보 -->
          <div class="grid grid-cols-2 gap-4">
            <div class="grid gap-2">
              <Label for="title">Title (EN)</Label>
              <Input id="title" v-model="editingItem.Title" />
            </div>
            <div class="grid gap-2">
              <Label for="title-kr">Title (KR)</Label>
              <Input id="title-kr" v-model="editingItem.Title_kr" />
            </div>
          </div>

          <div class="grid gap-2">
            <Label for="url">GitHub URL</Label>
            <Input id="url" v-model="editingItem.URL" type="url" />
          </div>

          <div class="grid gap-2">
            <Label for="categories">Categories (쉼표로 구분)</Label>
            <Input id="categories" v-model="editingItem.Categories" placeholder="Azure, Kubernetes, Container" />
          </div>

          <!-- 세션 설명 -->
          <div class="grid grid-cols-2 gap-4">
            <div class="grid gap-2">
              <Label for="desc">Description (EN)</Label>
              <textarea 
                id="desc"
                v-model="editingItem.Session_Description"
                class="min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            <div class="grid gap-2">
              <Label for="desc-kr">Description (KR)</Label>
              <textarea 
                id="desc-kr"
                v-model="editingItem.Session_Description_kr"
                class="min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
          </div>

          <div class="grid gap-2">
            <Label for="objectives">Learning Objectives</Label>
            <textarea 
              id="objectives"
              v-model="editingItem.Learning_Objectives"
              class="min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </div>

          <div class="grid gap-2">
            <Label for="modules">Lab Modules</Label>
            <Input id="modules" v-model="editingItem.Lab_Modules" />
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div class="grid gap-2">
              <Label for="tech">Technologies Used</Label>
              <Input id="tech" v-model="editingItem.Technologies_Used" />
            </div>
            <div class="grid gap-2">
              <Label for="prereq">Prerequisites</Label>
              <Input id="prereq" v-model="editingItem.Prerequisites" />
            </div>
          </div>

          <!-- 리소스 링크 -->
          <div class="border-t pt-4">
            <h3 class="font-header font-semibold text-sm mb-3 text-[var(--text-primary)]">리소스 링크</h3>
            <div class="grid grid-cols-2 gap-4">
              <div class="grid gap-2">
                <Label for="pptx">PPTX Link</Label>
                <Input id="pptx" v-model="editingItem.PPTX_Link" type="url" />
              </div>
              <div class="grid gap-2">
                <Label for="pdf">PDF Link</Label>
                <Input id="pdf" v-model="editingItem.PDF_Link" type="url" />
              </div>
              <div class="grid gap-2">
                <Label for="demo">Demo Link</Label>
                <Input id="demo" v-model="editingItem.Demo_Link" type="url" />
              </div>
              <div class="grid gap-2">
                <Label for="youtube">YouTube Link</Label>
                <Input id="youtube" v-model="editingItem.Youtube_Link" type="url" />
              </div>
            </div>
          </div>

          <!-- 메타 정보 -->
          <div class="border-t pt-4">
            <h3 class="font-header font-semibold text-sm mb-3 text-[var(--text-primary)]">메타 정보</h3>
            <div class="grid grid-cols-2 gap-4">
              <div class="grid gap-2">
                <Label for="contributor">Contributor</Label>
                <Input id="contributor" v-model="editingItem.Contributor" />
              </div>
              <div class="grid gap-2">
                <Label for="status">Status</Label>
                <select 
                  id="status"
                  v-model="editingItem.Status"
                  class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="pending">대기중</option>
                  <option value="processing">처리중</option>
                  <option value="completed">완료</option>
                  <option value="failed">실패</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter class="flex gap-2">
          <button 
            @click="isEditModalOpen = false"
            class="px-4 py-2.5 rounded-lg text-sm font-header font-semibold transition-all bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border)] hover:border-[var(--border-hover)]"
          >
            취소
          </button>
          <button 
            @click="saveEdit"
            class="px-4 py-2.5 rounded-lg text-sm font-header font-semibold transition-all bg-primary hover:bg-primary-hover text-white"
          >
            저장
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>