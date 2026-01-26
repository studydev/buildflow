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
  toggleSidebar: []
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
    <!-- 좌측: 사이드바 토글 + NexusSkill Platform 제목 -->
    <div class="flex items-center gap-3">
      <button 
        @click="$emit('toggleSidebar')"
        class="w-10 h-10 rounded-lg hover:bg-[var(--bg-tertiary)] flex items-center justify-center transition-all"
        title="Toggle Sidebar"
      >
        ☰
      </button>
      <div class="flex items-center gap-2">
        <div class="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-white font-header font-bold text-sm">
          WP
        </div>
        <span class="font-header font-bold text-lg" :class="isDarkMode ? 'text-white' : 'text-primary'">NexusSkill Platform</span>
      </div>
    </div>
    
    <!-- 우측: 다크모드 + 로그인/사용자 정보 -->
    <div class="flex items-center gap-3">
      <!-- Contributor 링크 (contributor 권한 있을 때만) -->
      <router-link 
        v-if="isContributor"
        to="/contributor/manage"
        class="px-3 py-2 text-sm font-medium text-[var(--text-secondary)] hover:text-primary transition-colors"
      >
        Repos
      </router-link>

      <button 
        @click="$emit('toggleDarkMode')"
        class="w-10 h-10 rounded-lg hover:bg-[var(--bg-tertiary)] flex items-center justify-center transition-all"
      >
        {{ isDarkMode ? '🌙' : '☀️' }}
      </button>

      <!-- 로그인 안된 경우 -->
      <button 
        v-if="!isAuthenticated"
        @click="openLogin"
        class="px-4 py-2 text-sm font-header font-semibold bg-primary hover:bg-primary-hover text-white rounded-lg transition-all"
      >
        로그인
      </button>
      
      <!-- 로그인된 경우 -->
      <div v-else class="relative">
        <button 
          @click="showUserMenu = !showUserMenu"
          @mouseenter="showUserMenu = true"
          class="px-4 py-2 text-sm font-header font-medium text-[var(--text-primary)] hover:text-primary transition-colors border border-[var(--border)] rounded-lg hover:border-primary flex items-center gap-2"
        >
          <span class="w-6 h-6 bg-primary/20 text-primary rounded-full flex items-center justify-center text-xs font-bold">
            {{ displayName ? displayName?.[0]?.toUpperCase() : 'U' }}
          </span>
          {{ displayName }}
        </button>
        
        <!-- 드롭다운 메뉴 -->
        <div 
          v-if="showUserMenu"
          @mouseleave="showUserMenu = false"
          class="absolute top-full right-0 mt-2 w-48 bg-[var(--card-bg)] border border-[var(--border)] rounded-lg shadow-lg py-2 z-50"
        >
          <div class="px-4 py-2 border-b border-[var(--border)]">
            <p class="text-xs text-[var(--text-secondary)]">로그인됨</p>
            <p class="text-sm font-medium text-[var(--text-primary)] truncate">{{ userEmail }}</p>
          </div>
          <button 
            @click="handleLogout"
            class="w-full px-4 py-2 text-left text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
          >
            로그아웃
          </button>
        </div>
      </div>
    </div>
  </header>

  <AuthModals ref="authModals" @login="handleLogin" />
</template>