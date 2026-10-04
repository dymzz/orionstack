<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink to="/" class="brand-link"><h1>OrionStack</h1></RouterLink>
      <nav class="app-nav">
        <RouterLink to="/" class="nav-link" exact-active-class="nav-link-active">工作台</RouterLink>
        <RouterLink v-if="authenticated" to="/data" class="nav-link">数据与备份</RouterLink>
        <RouterLink v-if="authenticated" to="/logs/retrieval" class="nav-link">日志</RouterLink>
        <RouterLink v-if="authenticated && currentRole === 'admin'" to="/admin/account" class="nav-link">后台</RouterLink>
        <button v-if="authenticated" class="nav-link nav-button" @click="handleLogout">退出 {{ currentUsername }}</button>
      </nav>
    </header>
    <main class="app-main"><RouterView /></main>
    <p v-if="logoutError" role="alert" class="error-message">{{ logoutError }}</p>
    <ToastContainer />
  </div>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { logout, useAuthState } from './modules/account'
import ToastContainer from './components/common/ToastContainer.vue'
import { errorMessage } from './shared/http'
const router = useRouter()
const { authenticated, currentUsername, currentRole } = useAuthState()
watch(authenticated, value => { if (!value && router.currentRoute.value.name !== 'login') router.replace('/login') })
const logoutError = ref('')
async function handleLogout() {
  logoutError.value = ''
  try { await logout(); await router.replace('/login') } catch (error) { logoutError.value = errorMessage(error) }
}
</script>
