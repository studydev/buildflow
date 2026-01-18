<script setup lang="ts">
import { ref } from 'vue'
import Sidebar from '@/components/layout/Sidebar.vue'
import Header from '@/components/layout/Header.vue'

const isDarkMode = ref(false)
const userEmail = ref<string | null>(null)
const isSidebarOpen = ref(true)

const toggleDarkMode = () => {
  isDarkMode.value = !isDarkMode.value
  if (isDarkMode.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

const handleLogin = (email: string) => {
  userEmail.value = email
}

const handleLogout = () => {
  userEmail.value = null
}
</script>

<template>
  <div class="flex flex-col h-screen overflow-hidden">
    <!-- 헤더 -->
    <Header 
      @toggle-dark-mode="toggleDarkMode"
      @toggle-sidebar="toggleSidebar"
      @login="handleLogin"
      @logout="handleLogout"
      :is-dark-mode="isDarkMode" 
      :user-email="userEmail"
    />
    
    <!-- 하단: 좌측 사이드바 + 우측 본문 -->
    <div class="flex flex-1 overflow-hidden">
      <Sidebar :is-dark-mode="isDarkMode" :is-open="isSidebarOpen" />
      
      <main class="flex-1 overflow-y-auto bg-[var(--bg-secondary)] p-8">
        <router-view />
      </main>
    </div>
  </div>
</template>