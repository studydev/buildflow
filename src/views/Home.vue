<script setup lang="ts">
import ContentGrid from '@/components/ContentGrid.vue'
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
          placeholder="Search workshops, tutorials, and resources..."
          class="w-full pl-11 pr-4 py-3 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
        />
      </div>
    </div>

    <div class="mb-8">
      <h1 class="font-header text-3xl font-bold text-[var(--text-primary)] mb-2">
        Recommended Learning Paths
      </h1>
      <p class="text-[var(--text-secondary)]">
        Curated workshops and tutorials to accelerate your technical skills
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
        Workshops
      </button>
      <button class="px-4 py-2 rounded-full text-sm font-header font-medium bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-primary hover:text-primary transition-colors">
        Tutorials
      </button>
      <button class="px-4 py-2 rounded-full text-sm font-header font-medium bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text-secondary)] hover:border-primary hover:text-primary transition-colors">
        Beginner
      </button>
    </div>

    <ContentGrid />
  </div>
</template>