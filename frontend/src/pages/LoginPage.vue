<template>
  <section class="card login-card">
    <div class="login-head">
      <p class="login-eyebrow">OrionStack</p>
      <h2>登录</h2>
      <p class="login-subtitle">请输入账号密码以继续使用。</p>
    </div>

    <form class="login-form" @submit.prevent="submit">
      <label class="label" for="username">用户名</label>
      <input
        id="username"
        v-model="username"
        class="text-input"
        autocomplete="username"
        required
      />

      <label class="label" for="password">密码</label>
      <input
        id="password"
        v-model="password"
        class="text-input"
        type="password"
        autocomplete="current-password"
        required
      />

      <button class="primary-button" type="submit" :disabled="loading">
        {{ loading ? '登录中...' : '登录' }}
      </button>
    </form>

    <p v-if="message" class="login-message">{{ message }}</p>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../services/auth'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)
const message = ref('')

async function submit() {
  loading.value = true
  message.value = ''
  try {
    await login(username.value, password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
  } catch (error) {
    message.value = error instanceof Error ? error.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>