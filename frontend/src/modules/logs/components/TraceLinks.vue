<template>
  <details><summary>查询追踪</summary>
    <dl class="facts"><dt>请求</dt><dd class="identifier">{{ requestId }}</dd><template v-if="eventId"><dt>原始召回</dt><dd class="identifier">{{ eventId }}</dd></template><template v-if="runId"><dt>后处理</dt><dd class="identifier">{{ runId }}</dd></template></dl>
    <RouterLink :to="{ path: '/logs/retrieval', query: { request_id: requestId, event_id: eventId, run_id: runId } }">查看本次审计</RouterLink>
  </details>
</template>
<script setup lang="ts">
import { RouterLink } from 'vue-router'
defineProps<{ requestId: string; eventId?: string | null; runId?: string | null }>()
</script>
