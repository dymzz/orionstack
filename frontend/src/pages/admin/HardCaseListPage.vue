<template>
  <div>
    <div class="admin-page-head">
      <div>
        <h2>Hard Cases</h2>
        <p class="admin-subtitle">自动捕获的 fallback / 负反馈案例，含 issue 分类与溯源信息。</p>
      </div>
      <button class="ghost-button" :disabled="loading" @click="fetchCases">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <p v-if="message" class="admin-message">{{ message }}</p>
    <p v-if="!loading && cases.length === 0" class="admin-empty">暂无 hard case 记录。</p>

    <div v-else class="admin-card-list">
      <section v-for="item in cases" :key="item.trace_id" class="card admin-case-card">
        <div class="admin-case-head">
          <div class="admin-case-badges">
            <span class="badge" :class="feedbackClass(item.user_feedback)">{{ item.user_feedback || '自动' }}</span>
            <span v-if="item.issue_category" class="badge badge-issue">{{ item.issue_category }}</span>
            <span v-if="item.fallback_reason" class="badge badge-status-fallback">{{ item.fallback_reason }}</span>
          </div>
          <code class="admin-trace-id">{{ item.trace_id }}</code>
        </div>
        <p class="admin-case-query">{{ item.raw_query }}</p>
        <dl class="admin-case-meta">
          <div v-if="item.router_used"><dt>router</dt><dd>{{ item.router_used }}</dd></div>
          <div v-if="item.domain_hint"><dt>domain</dt><dd>{{ item.domain_hint }}</dd></div>
          <div v-if="item.source_record_id"><dt>source_record</dt><dd><code>{{ item.source_record_id }}</code></dd></div>
          <div v-if="item.import_batch_id"><dt>batch</dt><dd><code>{{ item.import_batch_id }}</code></dd></div>
          <div v-if="item.unit_version"><dt>version</dt><dd>{{ item.unit_version }}</dd></div>
          <div v-if="item.dynamic_query_key"><dt>dq_key</dt><dd>{{ item.dynamic_query_key }}</dd></div>
          <div v-if="item.created_at"><dt>时间</dt><dd>{{ formatTime(item.created_at) }}</dd></div>
        </dl>
        <details v-if="item.evidence_spans && item.evidence_spans.length > 0" class="record-details">
          <summary>evidence spans ({{ item.evidence_spans.length }})</summary>
          <ul class="admin-span-list">
            <li v-for="(span, i) in item.evidence_spans" :key="i">{{ span.text }}</li>
          </ul>
        </details>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listHardCases } from '../../services/admin'
import type { HardCaseItem } from '../../types/admin'

const loading = ref(false)
const message = ref('')
const cases = ref<HardCaseItem[]>([])

async function fetchCases() {
  loading.value = true
  message.value = ''
  try {
    const result = await listHardCases(100)
    cases.value = result.items
  } catch (error) {
    message.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function feedbackClass(fb?: string | null) {
  if (fb === 'down') return 'badge-status-refused'
  return 'badge-status-system'
}

function formatTime(value: string) {
  const t = new Date(value)
  return Number.isNaN(t.getTime()) ? value : t.toLocaleString()
}

onMounted(() => { void fetchCases() })
</script>
