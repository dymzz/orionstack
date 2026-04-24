<template>
  <div>
    <div class="admin-page-head">
      <div>
        <h2>Debug</h2>
        <p class="admin-subtitle">最近问答记录 + 完整 debug 上下文。</p>
      </div>
      <div class="admin-actions">
        <button class="ghost-button" :disabled="loading" @click="refresh">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <p v-if="message" class="admin-message">{{ message }}</p>
    <p v-if="!loading && records.length === 0" class="admin-empty">暂无记录。</p>

    <div v-else class="admin-card-list">
      <section v-for="record in records" :key="record.trace_id" class="card admin-case-card">
        <div class="admin-case-head">
          <div class="admin-case-badges">
            <span class="badge" :class="statusClass(record.response_status)">{{ record.response_status }}</span>
            <span v-if="record.feedback_label" class="badge badge-issue">{{ record.feedback_label }}</span>
          </div>
          <code class="admin-trace-id">{{ record.trace_id }}</code>
        </div>
        <p class="admin-case-query">{{ record.raw_query }}</p>
        <p class="record-summary">
          {{ formatTime(record.created_at) }}
          <span> · chunks: {{ record.retrieved_chunk_ids.length }}</span>
        </p>

        <button class="ghost-button admin-expand-btn" @click="toggleDebug(record.trace_id)">
          {{ expandedId === record.trace_id ? '收起 Debug' : '展开 Debug' }}
        </button>

        <div v-if="expandedId === record.trace_id && debugMap[record.trace_id]" class="admin-debug-detail">
          <DebugPanel
            :trace-id="record.trace_id"
            :response-status="record.response_status"
            :debug-info="debugMap[record.trace_id]!.debugInfo"
            :clarification-required="debugMap[record.trace_id]!.clarificationRequired"
            :clarification-question="debugMap[record.trace_id]!.clarificationQuestion"
          />
        </div>
        <div v-if="expandedId === record.trace_id && debugLoading" class="admin-empty">加载中...</div>
        <div v-if="expandedId === record.trace_id && debugError" class="error-box">{{ debugError }}</div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listChatRecords } from '../../services/chat'
import { getTrace } from '../../services/admin'
import DebugPanel from '../../components/chat/DebugPanel.vue'
import type { ChatRecordItem } from '../../types/chat'
import type { DebugInfo } from '../../types/chat'

interface DebugEntry {
  debugInfo: DebugInfo
  clarificationRequired?: boolean
  clarificationQuestion?: string
}

const loading = ref(false)
const message = ref('')
const records = ref<ChatRecordItem[]>([])
const expandedId = ref('')
const debugMap = ref<Record<string, DebugEntry>>({})
const debugLoading = ref(false)
const debugError = ref('')

async function refresh() {
  loading.value = true
  message.value = ''
  try {
    const result = await listChatRecords(30)
    records.value = result.items
  } catch (error) {
    message.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function toggleDebug(traceId: string) {
  if (expandedId.value === traceId) {
    expandedId.value = ''
    return
  }
  expandedId.value = traceId
  debugError.value = ''
  if (debugMap.value[traceId]) return

  debugLoading.value = true
  try {
    const trace = await getTrace(traceId)
    const debugInfo: DebugInfo = {
      normalized_query: trace.normalized_query,
      route_result: trace.intent || '',
      router_used: trace.router_used || '',
      retrieved_chunks: trace.retrieved_chunks,
      route_confidence: undefined,
      retrieval_score: trace.retrieval_score ?? undefined,
      fusion_score: trace.fusion_score ?? undefined,
      fallback_reason: trace.fallback_reason,
      domain_hint: trace.domain_hint,
      lexical_terms: null,
      semantic_expansions: null,
      planner_confidence: null,
    }
    debugMap.value[traceId] = {
      debugInfo,
      clarificationRequired: false,
      clarificationQuestion: undefined,
    }
  } catch (error) {
    debugError.value = error instanceof Error ? error.message : '加载 trace 失败'
  } finally {
    debugLoading.value = false
  }
}

function statusClass(status: string) {
  if (status === 'ok') return 'badge-status-ok'
  if (status === 'fallback') return 'badge-status-fallback'
  if (status === 'refused') return 'badge-status-refused'
  return 'badge-status-system'
}

function formatTime(value: string) {
  const t = new Date(value)
  return Number.isNaN(t.getTime()) ? value : t.toLocaleString()
}

onMounted(() => { void refresh() })
</script>
