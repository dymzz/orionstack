<template>
  <div>
    <div class="admin-page-head">
      <div>
        <h2>检索 Trace</h2>
        <p class="admin-subtitle">输入 trace_id 查看完整检索链路。</p>
      </div>
    </div>

    <div class="card admin-search-bar">
      <input
        v-model="traceIdInput"
        class="admin-input"
        type="text"
        placeholder="输入 trace_id 后回车查询"
        @keydown.enter.prevent="fetchTrace"
      />
      <button class="primary-button" :disabled="loading || !traceIdInput.trim()" @click="fetchTrace">
        {{ loading ? '查询中...' : '查询' }}
      </button>
    </div>

    <p v-if="errorMessage" class="error-box">{{ errorMessage }}</p>

    <section v-if="trace" class="card admin-detail-card">
      <div class="admin-detail-head">
        <span class="badge" :class="statusClass(trace.final_status)">{{ trace.final_status }}</span>
        <code class="admin-trace-id">{{ trace.trace_id }}</code>
      </div>

      <dl class="admin-grid">
        <div class="debug-item">
          <dt>raw_query</dt>
          <dd>{{ trace.raw_query }}</dd>
        </div>
        <div class="debug-item">
          <dt>normalized_query</dt>
          <dd>{{ trace.normalized_query }}</dd>
        </div>
        <div class="debug-item">
          <dt>intent</dt>
          <dd>{{ trace.intent || '无' }}</dd>
        </div>
        <div class="debug-item">
          <dt>router_used</dt>
          <dd>{{ trace.router_used || '无' }}</dd>
        </div>
        <div class="debug-item">
          <dt>retrieval_mode</dt>
          <dd>{{ trace.retrieval_mode || '无' }}</dd>
        </div>
        <div class="debug-item">
          <dt>retrieval_score</dt>
          <dd>{{ formatNum(trace.retrieval_score) }}</dd>
        </div>
        <div class="debug-item">
          <dt>fusion_score</dt>
          <dd>{{ formatNum(trace.fusion_score) }}</dd>
        </div>
        <div class="debug-item">
          <dt>domain_hint</dt>
          <dd>{{ trace.domain_hint || '无' }}</dd>
        </div>
        <div class="debug-item">
          <dt>fallback_reason</dt>
          <dd>{{ trace.fallback_reason || '无' }}</dd>
        </div>
        <div class="debug-item">
          <dt>source_record_id</dt>
          <dd>{{ trace.source_record_id || '无' }}</dd>
        </div>
        <div class="debug-item">
          <dt>import_batch_id</dt>
          <dd>{{ trace.import_batch_id || '无' }}</dd>
        </div>
        <div class="debug-item">
          <dt>unit_version</dt>
          <dd>{{ trace.unit_version ?? '无' }}</dd>
        </div>
        <div class="debug-item">
          <dt>dynamic_query_key</dt>
          <dd>{{ trace.dynamic_query_key || '无' }}</dd>
        </div>
        <div class="debug-item debug-item-wide">
          <dt>retrieved_chunks</dt>
          <dd>
            <code v-if="trace.retrieved_chunks.length">{{ trace.retrieved_chunks.join(', ') }}</code>
            <span v-else class="debug-empty">无</span>
          </dd>
        </div>
        <div class="debug-item debug-item-wide">
          <dt>citations</dt>
          <dd>
            <span v-if="!trace.citations.length" class="debug-empty">无</span>
            <ul v-else class="admin-citation-list">
              <li v-for="c in trace.citations" :key="c.citation_id">
                <strong>{{ c.source_label }}</strong>
                <code>{{ c.citation_id }}</code>
                <p class="citation-snippet">{{ c.snippet }}</p>
              </li>
            </ul>
          </dd>
        </div>
        <div class="debug-item">
          <dt>created_at</dt>
          <dd>{{ trace.created_at || '无' }}</dd>
        </div>
      </dl>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { getTrace } from '../../services/admin'
import type { TraceRecord } from '../../types/admin'

const traceIdInput = ref('')
const loading = ref(false)
const errorMessage = ref('')
const trace = ref<TraceRecord | null>(null)

async function fetchTrace() {
  const id = traceIdInput.value.trim()
  if (!id) return
  loading.value = true
  errorMessage.value = ''
  trace.value = null
  try {
    trace.value = await getTrace(id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '查询失败'
  } finally {
    loading.value = false
  }
}

function formatNum(v?: number | null) {
  return v != null ? v.toFixed(4) : '无'
}

function statusClass(status: string) {
  if (status === 'ok') return 'badge-status-ok'
  if (status === 'fallback') return 'badge-status-fallback'
  if (status === 'refused') return 'badge-status-refused'
  return 'badge-status-system'
}
</script>
