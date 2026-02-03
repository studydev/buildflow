<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthModals from '@/components/auth/AuthModals.vue'
import { useAuthStore } from '@/stores/auth'
import { redirectAfterLogin } from '@/router'

defineProps<{
  isDarkMode: boolean
}>()

const emit = defineEmits<{
  toggleDarkMode: []
}>()

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const authModals = ref<InstanceType<typeof AuthModals>>()
const showUserMenu = ref(false)

// Computed properties from auth store
const isAuthenticated = computed(() => authStore.isAuthenticated)
const userEmail = computed(() => authStore.user?.email || null)
const displayName = computed(() => authStore.user?.display_name || authStore.user?.email || null)
const isContributor = computed(() => authStore.isContributor)

const openLogin = () => {
  authModals.value?.openLogin()
}

const handleLogin = (_email: string) => {
  // Redirect to stored destination after login
  redirectAfterLogin()
}

const handleLogout = () => {
  authStore.logout()
  showUserMenu.value = false
  // Redirect to home if on a protected route
  if (route.meta.requiresAuth) {
    router.push({ name: 'Home' })
  }
}

// Auto-open login modal if redirected with login=required
onMounted(() => {
  if (route.query.login === 'required' && !isAuthenticated.value) {
    openLogin()
    // Clean up query param
    router.replace({ query: { ...route.query, login: undefined } })
  }
})

// Watch for route changes that require login
watch(() => route.query.login, (newVal) => {
  if (newVal === 'required' && !isAuthenticated.value) {
    openLogin()
    router.replace({ query: { ...route.query, login: undefined } })
  }
})
</script>

<template>
  <header class="bg-[var(--header-bg)] border-b border-[var(--border)] px-8 py-4 flex items-center justify-between backdrop-blur-sm">
    <!-- Left: NexusSkill Platform title -->
    <div class="flex items-center gap-3">
      <div class="flex items-center gap-2">
        <div class="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-white font-header font-bold text-sm">
          WS
        </div>
        <span class="font-header font-bold text-lg" :class="isDarkMode ? 'text-white' : 'text-primary'">NexusSkill Platform</span>
      </div>
    </div>
    
    <!-- Right: Dark mode + Login/User info -->
    <div class="flex items-center gap-3">
      <!-- GitHub Repo Link -->
      <a
        href="https://github.com/studydev/buildflow"
        target="_blank"
        rel="noopener noreferrer"
        class="w-10 h-10 rounded-lg hover:bg-[var(--bg-tertiary)] flex items-center justify-center transition-all text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        title="GitHub Repository"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
        </svg>
      </a>

      <!-- Contributor link (contributor role only) -->
      <router-link 
        v-if="isContributor"
        to="/contributor/manage"
        class="w-10 h-10 rounded-lg hover:bg-[var(--bg-tertiary)] flex items-center justify-center transition-all text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        title="Manage Content"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 20h9"></path>
          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
        </svg>
      </router-link>

      <button 
        @click="$emit('toggleDarkMode')"
        class="w-10 h-10 rounded-lg hover:bg-[var(--bg-tertiary)] flex items-center justify-center transition-all"
      >
        {{ isDarkMode ? '🌙' : '☀️' }}
      </button>

      <!-- Not logged in -->
      <button 
        v-if="!isAuthenticated"
        @click="openLogin"
        class="px-4 py-2 text-sm font-header font-semibold bg-primary hover:bg-primary-hover text-white rounded-lg transition-all"
      >
        Sign In
      </button>
      
      <!-- Logged in - Hover to show Sign Out -->
      <button 
        v-else
        @mouseenter="showUserMenu = true"
        @mouseleave="showUserMenu = false"
        @click="showUserMenu ? handleLogout() : null"
        class="px-4 py-2 text-sm font-header font-medium transition-colors border rounded-lg flex items-center gap-2"
        :class="showUserMenu 
          ? 'text-red-500 border-red-300 hover:bg-red-50 dark:hover:bg-red-900/20' 
          : 'text-[var(--text-primary)] border-[var(--border)] hover:border-primary'"
      >
        <span 
          class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
          :class="showUserMenu ? 'bg-red-100 text-red-500' : 'bg-primary/20 text-primary'"
        >
          {{ showUserMenu ? '→' : (displayName ? displayName?.[0]?.toUpperCase() : 'U') }}
        </span>
        <span class="inline-block" :style="{ minWidth: displayName ? `${displayName.length * 0.55}em` : '5em' }">
          {{ showUserMenu ? 'Sign Out' : displayName }}
        </span>
      </button>
    </div>
  </header>

  <AuthModals ref="authModals" @login="handleLogin" />
</template>