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
  { icon: 'github', label: 'GitHub Repo', path: '/' },
  { icon: 'youtube', label: 'YouTube', path: '/contents/youtube' },
  // { icon: '📚', label: 'Workshops (예정)', path: '/workshops' },
]

const categories = [
  { icon: 'github', label: 'GitHub Repo', path: '/contributor/manage' },
  { icon: 'youtube', label: 'YouTube', path: '/contributor/youtube' },
  // { icon: '📚', label: 'Workshops', path: '/contributor/manage' },
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
          <span class="w-5 h-5 flex items-center justify-center">
            <svg v-if="item.icon === 'github'" class="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
            <svg v-else-if="item.icon === 'youtube'" class="w-4 h-4 flex-shrink-0 text-red-500" fill="currentColor" viewBox="0 0 24 24"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
            <template v-else>{{ item.icon }}</template>
          </span>
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
          <span class="w-5 h-5 flex items-center justify-center">
            <svg v-if="category.icon === 'github'" class="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
            <svg v-else-if="category.icon === 'youtube'" class="w-4 h-4 flex-shrink-0 text-red-500" fill="currentColor" viewBox="0 0 24 24"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
            <template v-else>{{ category.icon }}</template>
          </span>
          <span>{{ category.label }}</span>
        </router-link>
      </div>
    </nav>
  </aside>
</template>