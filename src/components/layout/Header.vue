<script setup lang="ts">
import { ref } from 'vue'
import AuthModals from '@/components/auth/AuthModals.vue'

defineProps<{
  isDarkMode: boolean
  userEmail: string | null
}>()

const emit = defineEmits<{
  toggleDarkMode: []
  toggleSidebar: []
  login: [email: string]
  logout: []
}>()

const authModals = ref<InstanceType<typeof AuthModals>>()
const showUserMenu = ref(false)

const openLogin = () => {
  authModals.value?.openLogin()
}

const handleLogin = (email: string) => {
  emit('login', email)
}

const handleLogout = () => {
  emit('logout')
  showUserMenu.value = false
}
</script>

<template>
  <header class="bg-[var(--header-bg)] border-b border-[var(--border)] px-8 py-4 flex items-center justify-between backdrop-blur-sm">
    <!-- 좌측: 사이드바 토글 + Workshop Platform 제목 -->
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
        <span class="font-header font-bold text-lg" :class="isDarkMode ? 'text-white' : 'text-primary'">Workshop Platform</span>
      </div>
    </div>
    
    <!-- 우측: 다크모드 + 로그인/사용자 정보 -->
    <div class="flex items-center gap-3">
      <button 
        @click="$emit('toggleDarkMode')"
        class="w-10 h-10 rounded-lg hover:bg-[var(--bg-tertiary)] flex items-center justify-center transition-all"
      >
        {{ isDarkMode ? '🌙' : '☀️' }}
      </button>

      <!-- 로그인 안된 경우 -->
      <button 
        v-if="!userEmail"
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
          class="px-4 py-2 text-sm font-header font-medium text-[var(--text-primary)] hover:text-primary transition-colors border border-[var(--border)] rounded-lg hover:border-primary"
        >
          {{ userEmail }}
        </button>
        
        <!-- 드롭다운 메뉴 -->
        <div 
          v-if="showUserMenu"
          @mouseleave="showUserMenu = false"
          class="absolute top-full right-0 mt-2 w-48 bg-[var(--card-bg)] border border-[var(--border)] rounded-lg shadow-lg py-2 z-50"
        >
          <button 
            @click="handleLogout"
            class="w-full px-4 py-2 text-left text-sm text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            로그아웃
          </button>
        </div>
      </div>
    </div>
  </header>

  <AuthModals ref="authModals" @login="handleLogin" />
</template>