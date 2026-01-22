/**
 * API Client - Centralized HTTP client for backend communication
 * 
 * Features:
 * - Automatic Authorization header injection
 * - Token refresh on 401 responses
 * - Correlation ID header for request tracing
 * - Constitution-compliant response handling
 */

import { useAuthStore } from '@/stores/auth'
import type { AuthTokens } from '@/stores/auth'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_PREFIX = '/api/v1'

/**
 * Generate a UUID v4 for correlation ID
 */
function generateCorrelationId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/**
 * Constitution-compliant API response
 */
export interface APIResponse<T = unknown> {
  success: boolean
  data?: T
  error?: {
    code: string
    message: string
    details?: Array<{ field: string; issue: string }>
  }
  meta: {
    timestamp: string
    correlationId: string
  }
}

/**
 * API Error class with structured error information
 */
export class APIError extends Error {
  public readonly code: string
  public readonly status: number
  public readonly details?: Array<{ field: string; issue: string }>
  public readonly correlationId: string

  constructor(
    message: string,
    code: string,
    status: number,
    correlationId: string,
    details?: Array<{ field: string; issue: string }>
  ) {
    super(message)
    this.name = 'APIError'
    this.code = code
    this.status = status
    this.details = details
    this.correlationId = correlationId
  }
}

let isRefreshing = false
let refreshPromise: Promise<boolean> | null = null

/**
 * Attempt to refresh the access token
 */
async function refreshAccessToken(): Promise<boolean> {
  const authStore = useAuthStore()
  
  if (!authStore.refreshToken) {
    return false
  }

  // Prevent multiple simultaneous refresh attempts
  if (isRefreshing) {
    return refreshPromise!
  }

  isRefreshing = true
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}${API_PREFIX}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Correlation-ID': generateCorrelationId(),
        },
        body: JSON.stringify({
          refresh_token: authStore.refreshToken,
        }),
      })

      if (!response.ok) {
        authStore.logout()
        return false
      }

      const result: APIResponse<AuthTokens> = await response.json()
      
      if (result.success && result.data) {
        authStore.updateTokens(result.data)
        return true
      }

      authStore.logout()
      return false
    } catch {
      authStore.logout()
      return false
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()

  return refreshPromise
}

/**
 * Make an API request with automatic auth handling
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const authStore = useAuthStore()
  const correlationId = generateCorrelationId()

  // Build headers
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Correlation-ID': correlationId,
    ...authStore.getAuthHeader(),
  }

  // Merge with provided headers
  if (options.headers) {
    const optHeaders = options.headers as Record<string, string>
    Object.assign(headers, optHeaders)
  }

  const url = `${API_BASE_URL}${API_PREFIX}${endpoint}`

  // T026: Use credentials: 'include' for HttpOnly cookie auth
  let response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  })

  // Handle 401 - try to refresh token
  if (response.status === 401 && authStore.canRefresh) {
    const refreshed = await refreshAccessToken()
    
    if (refreshed) {
      // Retry with new token
      headers['Authorization'] = `Bearer ${authStore.accessToken}`
      response = await fetch(url, {
        ...options,
        headers,
        credentials: 'include',
      })
    }
  }

  const result: APIResponse<T> = await response.json()

  if (!result.success) {
    throw new APIError(
      result.error?.message || 'Unknown error',
      result.error?.code || 'UNKNOWN_ERROR',
      response.status,
      result.meta?.correlationId || correlationId,
      result.error?.details
    )
  }

  return result.data as T
}

/**
 * Convenience methods for common HTTP verbs
 */
export const api = {
  get<T>(endpoint: string): Promise<T> {
    return apiRequest<T>(endpoint, { method: 'GET' })
  },

  post<T>(endpoint: string, data?: unknown): Promise<T> {
    return apiRequest<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  },

  put<T>(endpoint: string, data?: unknown): Promise<T> {
    return apiRequest<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  },

  patch<T>(endpoint: string, data?: unknown): Promise<T> {
    return apiRequest<T>(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    })
  },

  delete<T>(endpoint: string): Promise<T> {
    return apiRequest<T>(endpoint, { method: 'DELETE' })
  },
}

/**
 * Auth-specific API calls
 */
export const authApi = {
  /**
   * Request OTP for email authentication
   */
  async requestOtp(email: string): Promise<{
    message: string
    email: string
    expires_in_seconds: number
  }> {
    return api.post('/auth/otp', { email })
  },

  /**
   * Verify OTP and get tokens
   */
  async verifyOtp(email: string, code: string): Promise<AuthTokens> {
    return api.post('/auth/verify', { email, code })
  },

  /**
   * Refresh access token
   */
  async refreshToken(refresh_token: string): Promise<AuthTokens> {
    return api.post('/auth/refresh', { refresh_token })
  },

  /**
   * Get current user profile
   */
  async getCurrentUser(): Promise<{
    id: string
    email: string
    display_name: string | null
    role: string
    created_at: string
  }> {
    return api.get('/users/me')
  },

  /**
   * T025: Get current user via auth endpoint (cookie-based)
   */
  async getMe(): Promise<{
    id: string
    email: string
    display_name: string | null
    role: string
    created_at: string
  }> {
    return api.get('/auth/me')
  },

  /**
   * T039: Logout - clears HttpOnly cookie on server
   */
  async logout(): Promise<void> {
    return api.post('/auth/logout')
  },
}

export default api
