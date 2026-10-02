<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="app-header-brand">
        <RouterLink to="/" class="brand-link">
          <h1>OrionStack</h1>
        </RouterLink>
      </div>
      <nav class="app-nav">
        <RouterLink to="/" class="nav-link" exact-active-class="nav-link-active">问答</RouterLink>
        <RouterLink v-if="isAdminRole" to="/admin" class="nav-link" active-class="nav-link-active">管理入口</RouterLink>
        <button v-if="authenticated" class="nav-link nav-button" @click="handleLogout">
          退出 {{ currentUsername }}
        </button>
      </nav>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
    <ToastContainer />
  </div>
</template>

<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import { useRouter } from 'vue-router'
import { logout, useAuthState } from './services/auth'
import ToastContainer from './components/common/ToastContainer.vue'

const router = useRouter()
const { authenticated, currentUsername, currentRole } = useAuthState()

const isAdminRole = currentRole

async function handleLogout() {
  await logout()
  await router.push('/login')
}
</script>