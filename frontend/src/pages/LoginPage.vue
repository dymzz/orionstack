<template>
  <section class="card login-card">
    <div class="login-head">
      <p class="login-eyebrow">Admin Access</p>
      <h2>登录管理入口</h2>
      <p class="admin-subtitle">Trace、Hard Case、抽取审核与调试记录需要管理员身份。</p>
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

    <p v-if="message" class="admin-message">{{ message }}</p>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../services/auth'

const route = useRoute()
const router = useRouter()
const username = ref('admin')
const password = ref('')
const loading = ref(false)
const message = ref('')

async function submit() {
  loading.value = true
  message.value = ''
  try {
    await login(username.value, password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/admin/traces'
    await router.replace(redirect)
  } catch (error) {
    message.value = error instanceof Error ? error.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>
