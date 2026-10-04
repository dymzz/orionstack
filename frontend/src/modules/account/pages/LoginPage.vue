<template>
  <section class="card login-card">
    <div class="login-head"><p class="login-eyebrow">OrionStack</p><h2>登录</h2></div>
    <p v-if="!config && !message">正在加载登录方式…</p>
    <template v-if="config?.mode === 'oidc'">
      <p class="login-subtitle">使用组织身份服务登录，认证与账号安全由身份提供方管理。</p>
      <button class="primary-button" @click="beginOidcLogin(returnPath)">使用组织账号登录</button>
    </template>
    <form v-if="config?.mode === 'demo'" class="login-form" @submit.prevent="submit">
      <p class="muted">当前为本地演示登录。</p>
      <div class="row"><button type="button" class="secondary-button" @click="username = 'admin'; password = 'admin'">填入 admin 演示身份</button><button type="button" class="secondary-button" @click="username = 'test'; password = 'test'">填入普通用户演示身份</button></div>
      <label class="label" for="username">用户名</label>
      <input id="username" v-model="username" class="text-input" autocomplete="username" required />
      <label class="label" for="password">密码</label>
      <input id="password" v-model="password" class="text-input" type="password" autocomplete="current-password" required />
      <button class="primary-button" type="submit" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
    </form>
    <p v-if="message" class="login-message" role="alert">{{ message }}</p>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login, getIdentityConfig, beginOidcLogin } from '../session'
import type { IdentityConfig } from '../session'
import { errorMessage } from '../../../shared/http'
const route = useRoute(); const router = useRouter()
const username = ref(''); const password = ref(''); const loading = ref(false); const message = ref('')
const config = ref<IdentityConfig | null>(null)
const returnPath = computed(() => {
  const path = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
  return path.startsWith('/') && !path.startsWith('//') && !path.includes('\\') ? path : '/'
})
onMounted(async () => { try { config.value = await getIdentityConfig() } catch (error) { message.value = errorMessage(error) } })
async function submit() {
  loading.value = true; message.value = ''
  try {
    if (!await login(username.value, password.value)) throw new Error('Session unavailable')
    password.value = ''; await router.replace(returnPath.value)
  } catch (error) { message.value = errorMessage(error) } finally { loading.value = false }
}
</script>
