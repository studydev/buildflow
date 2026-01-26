<script setup lang="ts">
import { useRoute } from 'vue-router'

defineProps<{
  isDarkMode: boolean
  isOpen: boolean
}>()

const route = useRoute()

const navItems = [
  { icon: '🎓', label: 'GitHub Repo', path: '/' },
  { icon: '📚', label: 'Workshops (예정)', path: '/workshops' },
]

const categories = [
  { icon: '📋', label: 'GitHub Repo', path: '/contributor/manage' },
  // { icon: '📋', label: 'Workshops', path: '/contributor/manage' },
]
</script>

<template>
  <aside 
    :class="[
      'bg-[var(--sidebar-bg)] border-r border-[var(--border)] flex flex-col transition-all duration-300',
      isOpen ? 'w-64' : 'w-0 border-r-0'
    ]"
  >
    <nav :class="['flex-1 overflow-y-auto', !isOpen && 'opacity-0']">
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