/**
 * Auth Store - Manages authentication state
 * 
 * Features:
 * - JWT token management (access & refresh)
 * - User profile storage
 * - Automatic token refresh
 * - Persistent state (survives page reload)
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface User {
  id: string
  email: string
  display_name: string | null
  role: 'user' | 'contributor' | 'admin'
  created_at: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

interface TokenPayload {
  sub: string
  email: string
  role: string
  exp: number
  iat: number
}

/**
 * Parse JWT token to extract payload
 */
function parseJwt(token: string): TokenPayload | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const base64Url = parts[1]
    if (!base64Url) return null
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch {
    return null
  }
}

/**
 * Check if token is expired
 */
function isTokenExpired(token: string): boolean {
  const payload = parseJwt(token)
  if (!payload) return true
  // Add 30 second buffer to account for clock skew
  return payload.exp * 1000 < Date.now() + 30000
}

export const useAuthStore = defineStore('auth', () => {
  // State
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const user = ref<User | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  // Session validity flag for cookie-based auth (server confirmed)
  const sessionValid = ref(false)
  // Flag to track if initial session check has been done
  const sessionChecked = ref(false)

  // Getters
  const isAuthenticated = computed(() => {
    // Cookie-based auth: session is valid if server confirmed it
    // OR if we have a valid access token (for immediate post-login state)
    return sessionValid.value || (!!accessToken.value && !isTokenExpired(accessToken.value))
  })

  const needsRefresh = computed(() => {
    if (!accessToken.value) return false
    return isTokenExpired(accessToken.value)
  })

  const canRefresh = computed(() => {
    return !!refreshToken.value && !isTokenExpired(refreshToken.value)
  })

  const userRole = computed(() => user.value?.role || null)

  const isContributor = computed(() => {
    const role = userRole.value
    return role === 'contributor' || role === 'admin'
  })

  const isAdmin = computed(() => userRole.value === 'admin')

  // Actions
  function setTokens(tokens: AuthTokens) {
    accessToken.value = tokens.access_token
    refreshToken.value = tokens.refresh_token
  }

  function setUser(userData: User) {
    user.value = userData
  }

  function setError(message: string | null) {
    error.value = message
  }

  function setLoading(loading: boolean) {
    isLoading.value = loading
  }

  function login(tokens: AuthTokens, userData?: User) {
    setTokens(tokens)
    if (userData) {
      setUser(userData)
    } else {
      // Extract minimal user info from token
      const payload = parseJwt(tokens.access_token)
      if (payload) {
        user.value = {
          id: payload.sub,
          email: payload.email,
          display_name: null,
          role: payload.role as User['role'],
          created_at: new Date().toISOString(),
        }
      }
    }
    // Mark session as valid after successful login
    sessionValid.value = true
    sessionChecked.value = true
    error.value = null
  }

  function logout() {
    // T040: Call backend logout to clear HttpOnly cookie
    import('@/lib/api').then(({ authApi }) => {
      authApi.logout().catch(() => {
        // Ignore logout API errors - continue with local cleanup
      })
    })

    accessToken.value = null
    refreshToken.value = null
    user.value = null
    sessionValid.value = false
    error.value = null
  }

  function updateTokens(tokens: AuthTokens) {
    accessToken.value = tokens.access_token
    refreshToken.value = tokens.refresh_token
  }

  /**
   * Get authorization header for API requests
   */
  function getAuthHeader(): Record<string, string> {
    if (!accessToken.value) {
      return {}
    }
    return {
      Authorization: `Bearer ${accessToken.value}`,
    }
  }

  /**
   * T024: Check authentication status via API (cookie-based)
   * This validates the session with the server using HttpOnly cookie
   */
  async function checkSession(): Promise<boolean> {
    try {
      isLoading.value = true
      // Import api dynamically to avoid circular dependency
      const { authApi } = await import('@/lib/api')
      const userData = await authApi.getMe()

      // Update user state with server response
      user.value = {
        id: userData.id,
        email: userData.email,
        display_name: userData.display_name,
        role: userData.role as User['role'],
        created_at: userData.created_at,
      }

      // Mark session as valid (cookie-based auth confirmed by server)
      sessionValid.value = true
      sessionChecked.value = true
      return true
    } catch {
      // Session invalid - clear local state
      accessToken.value = null
      refreshToken.value = null
      user.value = null
      sessionValid.value = false
      sessionChecked.value = true
      return false
    } finally {
      isLoading.value = false
    }
  }

  return {
    // State
    accessToken,
    refreshToken,
    user,
    isLoading,
    error,
    sessionChecked,

    // Getters
    isAuthenticated,
    needsRefresh,
    canRefresh,
    userRole,
    isContributor,
    isAdmin,
    
    // Actions
    setTokens,
    setUser,
    setError,
    setLoading,
    login,
    logout,
    updateTokens,
    getAuthHeader,
    checkSession,
  }
}, {
  persist: {
    key: 'buildflow-auth',
    storage: localStorage,
    // T045: Only persist user info, tokens are now in HttpOnly cookies
    pick: ['user'],
  },
})
