<script setup lang="ts">
import { ref } from 'vue'
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

const isLoginOpen = ref(false)
const showSignupInLogin = ref(false)

const loginEmail = ref('')
const loginPassword = ref('')
const signupEmail = ref('')
const signupPassword = ref('')
const signupConfirmPassword = ref('')

const emit = defineEmits<{
  login: [email: string]
}>()

const handleLogin = () => {
  console.log('로그인:', { email: loginEmail.value, password: loginPassword.value })
  // 여기에 실제 로그인 로직 구현
  emit('login', loginEmail.value)
  isLoginOpen.value = false
  showSignupInLogin.value = false
  loginEmail.value = ''
  loginPassword.value = ''
}

const handleSignup = () => {
  if (signupPassword.value !== signupConfirmPassword.value) {
    alert('비밀번호가 일치하지 않습니다.')
    return
  }
  console.log('회원가입:', { email: signupEmail.value, password: signupPassword.value })
  // 여기에 실제 회원가입 로직 구현
  emit('login', signupEmail.value)
  isLoginOpen.value = false
  showSignupInLogin.value = false
  signupEmail.value = ''
  signupPassword.value = ''
  signupConfirmPassword.value = ''
}

const switchToSignup = () => {
  showSignupInLogin.value = true
}

const switchToLogin = () => {
  showSignupInLogin.value = false
}

defineExpose({
  openLogin: () => { 
    isLoginOpen.value = true
    showSignupInLogin.value = false
  }
})
</script>

<template>
  <!-- 로그인/회원가입 통합 모달 -->
  <Dialog v-model:open="isLoginOpen">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle class="text-xl font-header">
          {{ showSignupInLogin ? '회원가입' : '로그인' }}
        </DialogTitle>
        <DialogDescription>
          {{ showSignupInLogin ? '새 계정을 만들어 학습을 시작하세요.' : '계정에 로그인하여 학습을 시작하세요.' }}
        </DialogDescription>
      </DialogHeader>
      
      <!-- 로그인 폼 -->
      <div v-if="!showSignupInLogin" class="grid gap-4 py-4">
        <div class="grid gap-2">
          <Label for="login-email">이메일 주소</Label>
          <Input
            id="login-email"
            v-model="loginEmail"
            type="email"
            placeholder="example@email.com"
            autocomplete="email"
          />
        </div>
        <div class="grid gap-2">
          <Label for="login-password">비밀번호</Label>
          <Input
            id="login-password"
            v-model="loginPassword"
            type="password"
            placeholder="••••••••"
            autocomplete="current-password"
          />
        </div>
      </div>

      <!-- 회원가입 폼 -->
      <div v-else class="grid gap-4 py-4">
        <div class="grid gap-2">
          <Label for="signup-email">이메일 주소</Label>
          <Input
            id="signup-email"
            v-model="signupEmail"
            type="email"
            placeholder="example@email.com"
            autocomplete="email"
          />
        </div>
        <div class="grid gap-2">
          <Label for="signup-password">비밀번호</Label>
          <Input
            id="signup-password"
            v-model="signupPassword"
            type="password"
            placeholder="••••••••"
            autocomplete="new-password"
          />
        </div>
        <div class="grid gap-2">
          <Label for="signup-confirm-password">비밀번호 확인</Label>
          <Input
            id="signup-confirm-password"
            v-model="signupConfirmPassword"
            type="password"
            placeholder="••••••••"
            autocomplete="new-password"
          />
        </div>
      </div>

      <DialogFooter class="flex gap-2 w-full">
        <Button variant="outline" @click="isLoginOpen = false" class="flex-1">
          취소
        </Button>
        <Button 
          v-if="!showSignupInLogin"
          @click="handleLogin" 
          class="bg-primary hover:bg-primary-hover text-white flex-1"
        >
          로그인
        </Button>
        <Button 
          v-else
          @click="handleSignup" 
          class="bg-primary hover:bg-primary-hover text-white flex-1"
        >
          가입하기
        </Button>
      </DialogFooter>
      
      <div class="w-2/3 mx-auto border-t border-[var(--border)] mt-4 pt-4">
        <div class="text-center text-sm">
          <span class="text-muted-foreground">
            <template v-if="!showSignupInLogin">계정이 없으신가요? </template>
            <template v-else>이미 계정이 있으신가요? </template>
          </span>
          <button 
            v-if="!showSignupInLogin"
            @click="switchToSignup"
            class="text-primary hover:underline font-semibold transition-colors"
          >
            회원가입
          </button>
          <button 
            v-else
            @click="switchToLogin"
            class="text-primary hover:underline font-semibold transition-colors"
          >
            로그인
          </button>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>