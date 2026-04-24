<template>
  <div class="admin-layout">
    <nav class="admin-tabs">
      <RouterLink to="/admin/traces" class="admin-tab" active-class="admin-tab-active">Trace</RouterLink>
      <RouterLink to="/admin/hard-cases" class="admin-tab" active-class="admin-tab-active">Hard Cases</RouterLink>
      <RouterLink to="/admin/extraction" class="admin-tab" active-class="admin-tab-active">抽取审核</RouterLink>
      <RouterLink to="/admin/debug" class="admin-tab" active-class="admin-tab-active">Debug</RouterLink>
    </nav>
    <div class="admin-body">
      <RouterView />
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>
