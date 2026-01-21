import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from '../App.vue'

// Create a mock router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: { template: '<div>Home</div>' } },
  ],
})

describe('App.vue', () => {
  it('should mount without errors', async () => {
    // Setup Pinia
    const pinia = createPinia()
    setActivePinia(pinia)

    // Wait for router to be ready
    router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [pinia, router],
        stubs: {
          RouterView: true,
          RouterLink: true,
          Header: true,
          Sidebar: true,
        },
      },
    })
    expect(wrapper.exists()).toBe(true)
  })
})
