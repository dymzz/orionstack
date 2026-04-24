<template>
  <div class="collapsible-panel">
    <button class="collapsible-trigger" @click="open = !open">
      <span class="collapsible-title">{{ title }}</span>
      <span class="collapsible-badge">{{ badge }}</span>
      <span class="collapsible-arrow" :class="{ 'collapsible-arrow-open': open }">&#9660;</span>
    </button>
    <div v-if="open" class="collapsible-body">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  title: string
  badge?: string | number
}>()

const open = ref(false)
</script>
