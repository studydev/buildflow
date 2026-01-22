<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
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
        error.value = '내부 직원 전용 로그인 서비스입니다.'
      } else if (e.code === 'EMAIL_SEND_FAILED') {
        error.value = '이메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요.'
      } else if (e.code === 'VALIDATION_ERROR') {
        error.value = '올바른 이메일 형식을 입력해주세요.'
      } else if (e.code === 'RATE_LIMIT_EXCEEDED') {
        // Handle resend rate limit
        error.value = '잠시 후 다시 시도해주세요.'
      } else {
        error.value = e.message
      }
    } else {
      error.value = '인증 코드 요청에 실패했습니다. 다시 시도해주세요.'
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
        error.value = '인증 시도 횟수를 초과했습니다. 잠시 후 다시 시도해주세요.'
      } else {
        error.value = e.message
      }
    } else {
      error.value = '인증에 실패했습니다. 코드를 확인해주세요.'
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
        error.value = '잠시 후 다시 시도해주세요.'
      } else {
        error.value = e.message
      }
    } else {
      error.value = '인증 코드 재발송에 실패했습니다.'
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
          {{ step === 'email' ? '로그인' : '인증 코드 입력' }}
        </DialogTitle>
        <DialogDescription>
          {{ step === 'email' 
            ? '이메일 주소를 입력하면 인증 코드를 보내드립니다.' 
            : `${email}로 전송된 6자리 인증 코드를 입력해주세요.` 
          }}
        </DialogDescription>
      </DialogHeader>
      
      <!-- 에러 메시지 -->
      <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
        {{ error }}
      </div>
      
      <!-- 이메일 입력 단계 -->
      <div v-if="step === 'email'" class="grid gap-4 py-4">
        <div class="grid gap-2">
          <Label for="login-email">이메일 주소</Label>
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

      <!-- OTP 입력 단계 -->
      <div v-else class="grid gap-4 py-4">
        <div class="grid gap-2">
          <Label for="otp-code">인증 코드</Label>
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
            인증 코드는 {{ Math.floor(otpExpiresIn / 60) }}분간 유효합니다.
          </p>
        </div>
      </div>

      <DialogFooter class="flex gap-2 w-full">
        <Button variant="outline" @click="closeAndReset" class="flex-1" :disabled="isLoading">
          취소
        </Button>
        <Button 
          v-if="step === 'email'"
          @click="handleRequestOtp" 
          class="bg-primary hover:bg-primary-hover text-white flex-1"
          :disabled="!canSubmitEmail"
        >
          <span v-if="isLoading" class="flex items-center gap-2">
            <span class="animate-spin">⏳</span> 전송 중...
          </span>
          <span v-else>인증 코드 받기</span>
        </Button>
        <Button 
          v-else
          @click="handleVerifyOtp" 
          class="bg-primary hover:bg-primary-hover text-white flex-1"
          :disabled="!canSubmitOtp"
        >
          <span v-if="isLoading" class="flex items-center gap-2">
            <span class="animate-spin">⏳</span> 확인 중...
          </span>
          <span v-else>로그인</span>
        </Button>
      </DialogFooter>
      
      <!-- OTP 단계에서 다시 보내기 옵션 -->
      <div v-if="step === 'otp'" class="w-2/3 mx-auto border-t border-[var(--border)] mt-4 pt-4">
        <div class="text-center text-sm">
          <span class="text-muted-foreground">코드를 받지 못하셨나요? </span>
          <button 
            v-if="canResendOtp"
            @click="handleResendOtp"
            class="text-primary hover:underline font-semibold transition-colors"
            :disabled="isLoading"
          >
            다시 받기
          </button>
          <span v-else class="text-muted-foreground">
            {{ Math.floor(resendCountdown / 60) }}:{{ String(resendCountdown % 60).padStart(2, '0') }} 후 재발송 가능
          </span>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>