<script setup lang="ts">
import { ref, computed } from 'vue'
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
const otpExpiresIn = ref(300) // 5 minutes default
const devCode = ref<string | null>(null) // Development only - OTP code for testing

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
    devCode.value = result.dev_code || null
    step.value = 'otp'
  } catch (e) {
    if (e instanceof APIError) {
      error.value = e.message
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
  step.value = 'email'
  otpCode.value = ''
  error.value = null
}

const closeAndReset = () => {
  isLoginOpen.value = false
  step.value = 'email'
  email.value = ''
  otpCode.value = ''
  error.value = null
  isLoading.value = false
  devCode.value = null
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
        <!-- 개발 환경 전용: OTP 코드 표시 -->
        <div v-if="devCode" class="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
          <p class="text-xs text-yellow-700 font-semibold mb-1">🛠️ 개발 환경 전용</p>
          <p class="text-sm text-yellow-800">
            인증 코드: <code class="bg-yellow-100 px-2 py-1 rounded font-mono font-bold text-lg">{{ devCode }}</code>
          </p>
        </div>
        
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
            @click="handleResendOtp"
            class="text-primary hover:underline font-semibold transition-colors"
            :disabled="isLoading"
          >
            다시 받기
          </button>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>