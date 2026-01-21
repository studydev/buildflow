<script setup lang="ts">
import { computed } from 'vue'
import { useContentStore } from '@/stores/content'

const contentStore = useContentStore()

// Language options
const languages: { code: 'en' | 'ko'; label: string; name: string }[] = [
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'ko', label: 'KR', name: '한국어' },
]

// Get/set current language
const currentLanguage = computed({
  get: () => contentStore.displayLanguage,
  set: (val: 'en' | 'ko') => { contentStore.displayLanguage = val }
})
</script>

<template>
  <div class="flex items-center gap-1 bg-[var(--bg-secondary)] rounded-lg p-1 border border-[var(--border)]">
    <button
      v-for="lang in languages"
      :key="lang.code"
      @click="currentLanguage = lang.code"
      :class="[
        'px-3 py-1.5 rounded-md text-xs font-header font-semibold transition-all',
        currentLanguage === lang.code
          ? 'bg-primary text-white shadow-sm'
          : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]'
      ]"
      :title="lang.name"
    >
      {{ lang.label }}
    </button>
  </div>
</template>
