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
        <RouterLink to="/admin" class="nav-link" active-class="nav-link-active">管理入口</RouterLink>
      </nav>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>
