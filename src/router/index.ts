import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue')
  },
  {
    path: '/contributor/connect',
    name: 'CreateContent',
    component: () => import('@/views/contributor/CreateContent.vue')
  },
  {
    path: '/contributor/edit',
    name: 'ContributeContent',
    component: () => import('@/views/contributor/ContributeContent.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router