import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw, RouteLocationNormalized, NavigationGuardNext } from 'vue-router'

/**
 * Route meta interface for type safety
 */
declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    requiresContributor?: boolean
    requiresAdmin?: boolean
    title?: string
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: {
      title: 'NexusSkill - 학습 콘텐츠'
    }
  },
  {
    path: '/contributor/connect',
    name: 'CreateContent',
    component: () => import('@/views/contributor/CreateContent.vue'),
    meta: {
      requiresAuth: true,
      requiresContributor: true,
      title: 'GitHub 연결'
    }
  },
  {
    path: '/contributor/edit',
    name: 'ContributeContent',
    component: () => import('@/views/contributor/ContributeContent.vue'),
    meta: {
      requiresAuth: true,
      requiresContributor: true,
      title: '콘텐츠 편집'
    }
  },
  {
    path: '/content/:id/pipelines',
    name: 'PipelineHistory',
    component: () => import('@/views/contributor/PipelineHistory.vue'),
    meta: {
      requiresAuth: true,
      requiresContributor: true,
      title: '파이프라인 히스토리'
    }
  },
  // Catch-all 404 route
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/Home.vue'),
    meta: {
      title: '페이지를 찾을 수 없습니다'
    }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

/**
 * Navigation guard for authentication and authorization
 */
router.beforeEach(async (
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext
) => {
  // Update document title
  if (to.meta.title) {
    document.title = to.meta.title as string
  }

  // Lazy import to avoid circular dependency
  const { useAuthStore } = await import('@/stores/auth')
  const authStore = useAuthStore()

  // Check if route requires authentication
  if (to.meta.requiresAuth) {
    // Wait for session check to complete if not done yet
    if (!authStore.sessionChecked) {
      await authStore.checkSession()
    }

    if (!authStore.isAuthenticated) {
      // Store intended destination for redirect after login
      sessionStorage.setItem('redirectAfterLogin', to.fullPath)

      // T023: Show login required message (FR-013)
      sessionStorage.setItem('loginRequiredMessage', '이 기능을 사용하려면 로그인이 필요합니다')

      // Redirect to home with login prompt
      return next({
        name: 'Home',
        query: { login: 'required' }
      })
    }
  }

  // Check if route requires contributor role
  if (to.meta.requiresContributor) {
    if (!authStore.isContributor) {
      return next({
        name: 'Home',
        query: { error: 'contributor-required' }
      })
    }
  }

  // Check if route requires admin role
  if (to.meta.requiresAdmin) {
    if (!authStore.isAdmin) {
      return next({
        name: 'Home',
        query: { error: 'admin-required' }
      })
    }
  }

  next()
})

/**
 * After successful login, redirect to stored destination
 */
export function redirectAfterLogin(): void {
  const redirectPath = sessionStorage.getItem('redirectAfterLogin')
  if (redirectPath) {
    sessionStorage.removeItem('redirectAfterLogin')
    router.push(redirectPath)
  }
}

export default router