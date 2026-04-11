<template>
  <div class="panel">
    <h3>引用片段</h3>
    <p v-if="!citations.length" class="muted">当前回答没有引用。</p>
    <div v-else class="list">
      <article v-for="item in citations" :key="item.chunk_id" class="list-item">
        <h4>{{ item.document_name }}</h4>
        <p class="muted">文档ID: {{ item.document_id }}</p>
        <p>{{ item.snippet }}</p>
        <span class="badge">score: {{ Number(item.score).toFixed(3) }}</span>
      </article>
    </div>
  </div>
</template>

<script setup>
defineProps({
  citations: {
    type: Array,
    default: () => [],
  },
});
</script>
