<template>
  <div class="app-shell">
    <header class="topbar">
      <h1>OrionStack</h1>
      <p>Knowledge Assistant</p>
    </header>

    <nav class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <main>
      <KnowledgeAssistantPage v-if="activeTab === 'qa'" />
      <DocumentManagerPage v-else />
    </main>
  </div>
</template>

<script setup>
import { ref } from "vue";
import KnowledgeAssistantPage from "./pages/KnowledgeAssistantPage.vue";
import DocumentManagerPage from "./pages/DocumentManagerPage.vue";

const tabs = [
  { key: "qa", label: "知识问答" },
  { key: "docs", label: "文档管理" },
];

const activeTab = ref("qa");
</script>
