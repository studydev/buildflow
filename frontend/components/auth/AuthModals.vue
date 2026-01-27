<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuthStore } from '@/stores/auth'
import { authApi, APIError } from '@/lib/api'

const authStore = useAuthStore()

const isLoginOpen = ref(false)
const step = ref<'email' | 'otp'>('email')
const email = ref('')
const otpCode = ref('')
const isLoading = ref(false)
const error = ref<string | null>(null)
const otpExpiresIn = ref(180) // 3 minutes default

// T037: Countdown timer state for OTP resend limit
const resendCountdown = ref(0)
let countdownInterval: ReturnType<typeof setInterval> | null = null

// Start countdown timer when OTP is requested
const startResendCountdown = (seconds: number) => {
  resendCountdown.value = seconds
  
  if (countdownInterval) {
    clearInterval(countdownInterval)
  }
  
  countdownInterval = setInterval(() => {
    if (resendCountdown.value > 0) {
      resendCountdown.value--
    } else if (countdownInterval) {
      clearInterval(countdownInterval)
      countdownInterval = null
    }
  }, 1000)
}

// Cleanup interval on unmount
onUnmounted(() => {
  if (countdownInterval) {
    clearInterval(countdownInterval)
  }
})

const canResendOtp = computed(() => resendCountdown.value === 0 && !isLoading.value)

const emit = defineEmits<{
  login: [email: string]
}>()

const canSubmitEmail = computed(() => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email.value) && !isLoading.value
})

const canSubmitOtp = computed(() => {
  return otpCode.value.length === 6 && /^\d+$/.test(otpCode.value) && !isLoading.value
})

const handleRequestOtp = async () => {
  if (!canSubmitEmail.value) return
  
  isLoading.value = true
  error.value = null
  
  try {
    const result = await authApi.requestOtp(email.value)
    otpExpiresIn.value = result.expires_in_seconds
    step.value = 'otp'
    // T037: Start 3-minute resend countdown timer
    startResendCountdown(result.expires_in_seconds)
  } catch (e) {
    if (e instanceof APIError) {
      // T021: Handle domain validation errors
      if (e.code === 'DOMAIN_NOT_ALLOWED') {
        error.value = 'This service is for internal employees only.'
      } else if (e.code === 'EMAIL_SEND_FAILED') {
        error.value = 'Failed to send email. Please try again later.'
      } else if (e.code === 'VALIDATION_ERROR') {
        error.value = 'Please enter a valid email format.'
      } else if (e.code === 'RATE_LIMIT_EXCEEDED') {
        // Handle resend rate limit
        error.value = 'Please try again later.'
      } else {
        error.value = e.message
      }
    } else {
      error.value = 'Failed to request verification code. Please try again.'
    }
  } finally {
    isLoading.value = false
  }
}

const handleVerifyOtp = async () => {
  if (!canSubmitOtp.value) return
  
  isLoading.value = true
  error.value = null
  
  try {
    const tokens = await authApi.verifyOtp(email.value, otpCode.value)
    authStore.login(tokens)
    
    // Fetch user profile
    try {
      const user = await authApi.getCurrentUser()
      authStore.setUser({
        id: user.id,
        email: user.email,
        display_name: user.display_name,
        role: user.role as 'user' | 'contributor' | 'admin',
        created_at: user.created_at,
      })
    } catch {
      // User profile fetch failed, but login succeeded
      console.warn('Failed to fetch user profile')
    }
    
    emit('login', email.value)
    closeAndReset()
  } catch (e) {
    if (e instanceof APIError) {
      if (e.code === 'RATE_LIMIT_EXCEEDED') {
        error.value = 'Too many verification attempts. Please try again later.'
      } else {
        error.value = e.message
      }
    } else {
      error.value = 'Verification failed. Please check your code.'
    }
  } finally {
    isLoading.value = false
  }
}

const handleResendOtp = async () => {
  if (!canResendOtp.value) return
  
  // Re-request OTP (same as email step but without UI transition)
  isLoading.value = true
  error.value = null
  otpCode.value = ''
  
  try {
    const result = await authApi.requestOtp(email.value)
    otpExpiresIn.value = result.expires_in_seconds
    startResendCountdown(result.expires_in_seconds)
  } catch (e) {
    if (e instanceof APIError) {
      if (e.code === 'RATE_LIMIT_EXCEEDED') {
        error.value = 'Please try again later.'
      } else {
        error.value = e.message
      }
    } else {
      error.value = 'Failed to resend verification code.'
    }
  } finally {
    isLoading.value = false
  }
}

const closeAndReset = () => {
  isLoginOpen.value = false
  // Clear countdown on close
  if (countdownInterval) {
    clearInterval(countdownInterval)
    countdownInterval = null
  }
  resendCountdown.value = 0
  step.value = 'email'
  email.value = ''
  otpCode.value = ''
  error.value = null
  isLoading.value = false
}

defineExpose({
  openLogin: () => { 
    closeAndReset()
    isLoginOpen.value = true
  }
})
</script>

<template>
  <!-- 이메일 OTP 로그인 모달 -->
  <Dialog v-model:open="isLoginOpen">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle class="text-xl font-header">
          {{ step === 'email' ? 'Sign In' : 'Enter Verification Code' }}
        </DialogTitle>
        <DialogDescription>
          {{ step === 'email' 
            ? 'Enter your email address and we\'ll send you a verification code.' 
            : `Enter the 6-digit code sent to ${email}.` 
          }}
        </DialogDescription>
      </DialogHeader>
      
      <!-- 에러 메시지 -->
      <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
        {{ error }}
      </div>
      
      <!-- Email input step -->
      <div v-if="step === 'email'" class="grid gap-4 py-4">
        <div class="grid gap-2">
          <Label for="login-email">Email Address</Label>
          <Input
            id="login-email"
            v-model="email"
            type="email"
            placeholder="example@email.com"
            autocomplete="email"
            :disabled="isLoading"
            @keyup.enter="handleRequestOtp"
          />
        </div>
      </div>

      <!-- OTP input step -->
      <div v-else class="grid gap-4 py-4">
        <div class="grid gap-2">
          <Label for="otp-code">Verification Code</Label>
          <Input
            id="otp-code"
            v-model="otpCode"
            type="text"
            inputmode="numeric"
            pattern="[0-9]*"
            maxlength="6"
            placeholder="000000"
            autocomplete="one-time-code"
            :disabled="isLoading"
            @keyup.enter="handleVerifyOtp"
            class="text-center text-2xl tracking-widest font-mono"
          />
          <p class="text-xs text-muted-foreground text-center">
            This code is valid for {{ Math.floor(otpExpiresIn / 60) }} minutes.
          </p>
        </div>
      </div>

      <DialogFooter class="flex gap-2 w-full">
        <Button variant="outline" @click="closeAndReset" class="flex-1" :disabled="isLoading">
          Cancel
        </Button>
        <Button 
          v-if="step === 'email'"
          @click="handleRequestOtp" 
          class="bg-primary hover:bg-primary-hover text-white flex-1"
          :disabled="!canSubmitEmail"
        >
          <span v-if="isLoading" class="flex items-center gap-2">
            <span class="animate-spin">⏳</span> Sending...
          </span>
          <span v-else>Get Verification Code</span>
        </Button>
        <Button 
          v-else
          @click="handleVerifyOtp" 
          class="bg-primary hover:bg-primary-hover text-white flex-1"
          :disabled="!canSubmitOtp"
        >
          <span v-if="isLoading" class="flex items-center gap-2">
            <span class="animate-spin">⏳</span> Verifying...
          </span>
          <span v-else>Sign In</span>
        </Button>
      </DialogFooter>
      
      <!-- OTP resend option -->
      <div v-if="step === 'otp'" class="w-2/3 mx-auto border-t border-[var(--border)] mt-4 pt-4">
        <div class="text-center text-sm">
          <span class="text-muted-foreground">Didn't receive the code? </span>
          <button 
            v-if="canResendOtp"
            @click="handleResendOtp"
            class="text-primary hover:underline font-semibold transition-colors"
            :disabled="isLoading"
          >
            Resend
          </button>
          <span v-else class="text-muted-foreground">
            Resend available in {{ Math.floor(resendCountdown / 60) }}:{{ String(resendCountdown % 60).padStart(2, '0') }}
          </span>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>