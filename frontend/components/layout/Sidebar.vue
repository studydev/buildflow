<script setup lang="ts">
import { useRoute } from 'vue-router'

defineProps<{
  isDarkMode: boolean
  isOpen: boolean
}>()

const emit = defineEmits<{
  toggle: []
}>()

const route = useRoute()

const navItems = [
  { icon: '🎓', label: 'GitHub Repo', path: '/' },
  // { icon: '📚', label: 'Workshops (예정)', path: '/workshops' },
]

const categories = [
  { icon: '📋', label: 'GitHub Repo', path: '/contributor/manage' },
  // { icon: '📋', label: 'Workshops', path: '/contributor/manage' },
]
</script>

<template>
  <aside 
    :class="[
      'bg-[var(--sidebar-bg)] border-r border-[var(--border)] flex flex-col transition-all duration-300 relative',
      isOpen ? 'w-64' : 'w-0 border-r-0 overflow-hidden'
    ]"
  >
    <!-- Sidebar Toggle Button - inside sidebar, right aligned, vertically centered -->
    <button
      v-if="isOpen"
      @click="$emit('toggle')"
      class="absolute top-1/2 -translate-y-1/2 right-2 z-50 w-7 h-12 bg-[var(--bg-tertiary)]/60 hover:bg-[var(--bg-tertiary)] backdrop-blur-sm rounded-lg transition-all duration-200 flex items-center justify-center group hover:scale-105"
      title="Collapse Sidebar"
    >
      <svg 
        class="w-4 h-4 text-[var(--text-tertiary)] group-hover:text-[var(--text-secondary)] transition-colors"
        fill="none" 
        stroke="currentColor" 
        viewBox="0 0 24 24"
        stroke-width="2.5"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
        <path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7 7-7"/>
      </svg>
    </button>

    <!-- Expand button when sidebar is closed -->
    <button
      v-else
      @click="$emit('toggle')"
      class="fixed left-0 top-1/2 -translate-y-1/2 z-50 w-6 h-14 bg-[var(--card-bg)] border border-[var(--border)] border-l-0 rounded-r-xl shadow-lg hover:bg-[var(--bg-tertiary)] transition-all duration-200 flex items-center justify-center group hover:w-7"
      title="Expand Sidebar"
    >
      <svg 
        class="w-3 h-3 text-[var(--text-tertiary)] group-hover:text-[var(--text-secondary)] transition-colors"
        fill="none" 
        stroke="currentColor" 
        viewBox="0 0 24 24"
        stroke-width="2.5"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
        <path stroke-linecap="round" stroke-linejoin="round" d="M14 5l7 7-7 7"/>
      </svg>
    </button>

    <nav :class="['flex-1 overflow-y-auto', !isOpen && 'opacity-0 pointer-events-none']">
      <div class="p-3">
        <div class="text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-tertiary)] px-3 mb-2">
          Contents
        </div>
        <router-link
          v-for="item in navItems"
          :key="item.label"
          :to="item.path"
          :class="[
            'flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-all font-medium text-sm',
            route.path === item.path
              ? 'bg-primary text-white' 
              : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]'
          ]"
        >
          <span class="w-5 h-5 flex items-center justify-center">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </div>

      <div class="p-3">
        <div class="text-xs font-header font-semibold uppercase tracking-wider text-[var(--text-tertiary)] px-3 mb-2">
          Contributor
        </div>
        <router-link
          v-for="category in categories"
          :key="category.label"
          :to="category.path"
          :class="[
            'flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-all font-medium text-sm',
            route.path === category.path
              ? 'bg-primary text-white' 
              : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]'
          ]"
        >
          <span class="w-5 h-5 flex items-center justify-center">{{ category.icon }}</span>
          <span>{{ category.label }}</span>
        </router-link>
      </div>
    </nav>
  </aside>
</template>