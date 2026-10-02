<template>
  <section class="card debug-panel">
    <div class="debug-head">
      <div>
        <h2>Debug</h2>
        <p class="debug-subtitle">开发态最小调试上下文</p>
      </div>
      <button class="ghost-button" @click="copyDebugContext">
        {{ copyFeedback || '复制调试上下文' }}
      </button>
    </div>

    <dl class="debug-grid">
      <div class="debug-item">
        <dt>trace_id</dt>
        <dd>{{ traceId }}</dd>
      </div>
      <div class="debug-item">
        <dt>response_status</dt>
        <dd>{{ responseStatus }}</dd>
      </div>
      <div class="debug-item">
        <dt>normalized_query</dt>
        <dd>{{ debugInfo.normalized_query }}</dd>
      </div>
      <div class="debug-item">
        <dt>route_result</dt>
        <dd>{{ debugInfo.route_result }}</dd>
      </div>
      <div class="debug-item">
        <dt>router_used</dt>
        <dd>{{ debugInfo.router_used }}</dd>
      </div>
      <div class="debug-item">
        <dt>route_confidence</dt>
        <dd>{{ formatOptionalNumber(debugInfo.route_confidence) }}</dd>
      </div>
      <div class="debug-item">
        <dt>retrieval_score</dt>
        <dd>{{ formatOptionalNumber(debugInfo.retrieval_score) }}</dd>
      </div>
      <div class="debug-item">
        <dt>planner_confidence</dt>
        <dd>{{ formatOptionalNumber(debugInfo.planner_confidence) }}</dd>
      </div>
      <div class="debug-item">
        <dt>domain_hint</dt>
        <dd>{{ formatOptionalText(debugInfo.domain_hint) }}</dd>
      </div>
      <div class="debug-item debug-item-wide">
        <dt>fallback_reason</dt>
        <dd>{{ formatOptionalText(debugInfo.fallback_reason) }}</dd>
      </div>
      <div class="debug-item debug-item-wide">
        <dt>clarification_required</dt>
        <dd>{{ clarificationRequired ? '是' : '否' }}</dd>
      </div>
      <div
        v-if="clarificationRequired"
        class="debug-item debug-item-wide"
      >
        <dt>clarification_question</dt>
        <dd>{{ clarificationQuestion }}</dd>
      </div>
      <div class="debug-item debug-item-wide">
        <dt>lexical_terms</dt>
        <dd>
          <ul
            v-if="debugInfo.lexical_terms && debugInfo.lexical_terms.length > 0"
            class="debug-list"
          >
            <li v-for="term in debugInfo.lexical_terms" :key="term">
              <code>{{ term }}</code>
            </li>
          </ul>
          <span v-else class="debug-empty">无</span>
        </dd>
      </div>
      <div v-if="debugInfo.retrieval_mode" class="debug-item">
        <dt>retrieval_mode</dt>
        <dd>{{ debugInfo.retrieval_mode }}</dd>
      </div>
      <div v-if="debugInfo.fusion_score != null" class="debug-item">
        <dt>fusion_score</dt>
        <dd>{{ formatOptionalNumber(debugInfo.fusion_score) }}</dd>
      </div>
      <div v-if="debugInfo.rerank_accept != null" class="debug-item">
        <dt>rerank_accept</dt>
        <dd>{{ debugInfo.rerank_accept ? '是' : '否' }}</dd>
      </div>
      <div v-if="debugInfo.rerank_score != null" class="debug-item">
        <dt>rerank_score</dt>
        <dd>{{ formatOptionalNumber(debugInfo.rerank_score) }}</dd>
      </div>
      <div v-if="debugInfo.evidence_confidence != null" class="debug-item">
        <dt>evidence_confidence</dt>
        <dd>{{ formatOptionalNumber(debugInfo.evidence_confidence) }}</dd>
      </div>
      <div v-if="debugInfo.evidence_span_count != null" class="debug-item">
        <dt>evidence_span_count</dt>
        <dd>{{ debugInfo.evidence_span_count }}</dd>
      </div>
      <div v-if="debugInfo.reject_reason" class="debug-item debug-item-wide">
        <dt>reject_reason</dt>
        <dd>{{ debugInfo.reject_reason }}</dd>
      </div>
      <div v-if="debugInfo.source_record_id" class="debug-item">
        <dt>source_record_id</dt>
        <dd><code>{{ debugInfo.source_record_id }}</code></dd>
      </div>
      <div v-if="debugInfo.import_batch_id" class="debug-item">
        <dt>import_batch_id</dt>
        <dd><code>{{ debugInfo.import_batch_id }}</code></dd>
      </div>
      <div v-if="debugInfo.unit_version != null" class="debug-item">
        <dt>unit_version</dt>
        <dd>{{ debugInfo.unit_version }}</dd>
      </div>
      <div v-if="debugInfo.source_updated_at" class="debug-item">
        <dt>source_updated_at</dt>
        <dd>{{ debugInfo.source_updated_at }}</dd>
      </div>
      <div v-if="debugInfo.source_record_status" class="debug-item">
        <dt>source_record_status</dt>
        <dd>{{ debugInfo.source_record_status }}</dd>
      </div>
      <div v-if="debugInfo.dynamic_query_key" class="debug-item">
        <dt>dynamic_query_key</dt>
        <dd><code>{{ debugInfo.dynamic_query_key }}</code></dd>
      </div>
      <div v-if="debugInfo.freshness_status" class="debug-item">
        <dt>freshness_status</dt>
        <dd>{{ debugInfo.freshness_status }}</dd>
      </div>
      <div v-if="debugInfo.lexical_topk && debugInfo.lexical_topk.length > 0" class="debug-item debug-item-wide">
        <dt>lexical_topk</dt>
        <dd>
          <ul class="debug-list">
            <li v-for="c in debugInfo.lexical_topk" :key="c.unit_id">
              <code>{{ c.unit_id }}</code> ({{ c.score.toFixed(2) }})
            </li>
          </ul>
        </dd>
      </div>
      <div v-if="debugInfo.vector_topk && debugInfo.vector_topk.length > 0" class="debug-item debug-item-wide">
        <dt>vector_topk</dt>
        <dd>
          <ul class="debug-list">
            <li v-for="c in debugInfo.vector_topk" :key="c.unit_id">
              <code>{{ c.unit_id }}</code> ({{ c.score.toFixed(2) }})
            </li>
          </ul>
        </dd>
      </div>
      <div v-if="debugInfo.rrf_topk && debugInfo.rrf_topk.length > 0" class="debug-item debug-item-wide">
        <dt>rrf_topk</dt>
        <dd>
          <ul class="debug-list">
            <li v-for="c in debugInfo.rrf_topk" :key="c.unit_id">
              <code>{{ c.unit_id }}</code> ({{ c.score.toFixed(4) }})
            </li>
          </ul>
        </dd>
      </div>
      <div class="debug-item debug-item-wide">
        <dt>retrieved_chunks</dt>
        <dd>
          <ul v-if="debugInfo.retrieved_chunks.length > 0" class="debug-list">
            <li v-for="chunkId in debugInfo.retrieved_chunks" :key="chunkId">
              <code>{{ chunkId }}</code>
            </li>
          </ul>
          <span v-else class="debug-empty">无</span>
        </dd>
      </div>
    </dl>

    <details class="debug-raw">
      <summary>原始 JSON</summary>
      <pre>{{ debugInfoJson }}</pre>
    </details>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import type { DebugInfo } from '../../types/chat'

const props = defineProps<{
  traceId: string
  responseStatus: string
  debugInfo: DebugInfo
  clarificationRequired?: boolean
  clarificationQuestion?: string
}>()

const copyFeedback = ref('')

const debugInfoJson = computed(() => {
  return JSON.stringify(props.debugInfo, null, 2)
})

let copyFeedbackTimer: ReturnType<typeof setTimeout> | null = null

function formatOptionalNumber(value?: number | null) {
  if (value === undefined || value === null) return '无'
  return value.toFixed(2)
}

function formatOptionalText(value?: string | null) {
  return value && value.trim() ? value : '无'
}

function setCopyFeedback(message: string) {
  copyFeedback.value = message
  if (copyFeedbackTimer) clearTimeout(copyFeedbackTimer)
  copyFeedbackTimer = setTimeout(() => { copyFeedback.value = '' }, 2000)
}

function fallbackCopyText(text: string) {
  const textArea = document.createElement('textarea')
  textArea.value = text
  textArea.setAttribute('readonly', 'true')
  textArea.style.position = 'fixed'
  textArea.style.opacity = '0'
  document.body.appendChild(textArea)
  textArea.select()
  const copied = document.execCommand('copy')
  document.body.removeChild(textArea)
  return copied
}

function buildDebugContext() {
  const { debugInfo } = props
  const lines = [
    `trace_id: ${props.traceId}`,
    `response_status: ${props.responseStatus}`,
    `normalized_query: ${debugInfo.normalized_query}`,
    `route_result: ${debugInfo.route_result}`,
    `router_used: ${debugInfo.router_used}`,
    `route_confidence: ${formatOptionalNumber(debugInfo.route_confidence)}`,
    `retrieval_score: ${formatOptionalNumber(debugInfo.retrieval_score)}`,
    `fusion_score: ${formatOptionalNumber(debugInfo.fusion_score)}`,
    `planner_confidence: ${formatOptionalNumber(debugInfo.planner_confidence)}`,
    `domain_hint: ${formatOptionalText(debugInfo.domain_hint)}`,
    `fallback_reason: ${formatOptionalText(debugInfo.fallback_reason)}`,
    `retrieval_mode: ${debugInfo.retrieval_mode ?? '无'}`,
    `rerank_accept: ${debugInfo.rerank_accept != null ? (debugInfo.rerank_accept ? '是' : '否') : '无'}`,
    `rerank_score: ${formatOptionalNumber(debugInfo.rerank_score)}`,
    `evidence_confidence: ${formatOptionalNumber(debugInfo.evidence_confidence)}`,
    `evidence_span_count: ${debugInfo.evidence_span_count ?? '无'}`,
    `reject_reason: ${formatOptionalText(debugInfo.reject_reason)}`,
    `source_record_id: ${debugInfo.source_record_id ?? '无'}`,
    `import_batch_id: ${debugInfo.import_batch_id ?? '无'}`,
    `unit_version: ${debugInfo.unit_version ?? '无'}`,
    `source_updated_at: ${debugInfo.source_updated_at ?? '无'}`,
    `source_record_status: ${debugInfo.source_record_status ?? '无'}`,
    `dynamic_query_key: ${debugInfo.dynamic_query_key ?? '无'}`,
    `freshness_status: ${debugInfo.freshness_status ?? '无'}`,
    `clarification_required: ${props.clarificationRequired ? '是' : '否'}`,
    `clarification_question: ${props.clarificationQuestion ?? '无'}`,
    `lexical_terms: ${debugInfo.lexical_terms?.length ? debugInfo.lexical_terms.join(', ') : '无'}`,
    `retrieved_chunks: ${debugInfo.retrieved_chunks.length > 0 ? debugInfo.retrieved_chunks.join(', ') : '无'}`,
  ]
  if (debugInfo.lexical_topk?.length) {
    lines.push(`lexical_topk: ${debugInfo.lexical_topk.map(c => `${c.unit_id}(${c.score.toFixed(2)})`).join(', ')}`)
  }
  if (debugInfo.vector_topk?.length) {
    lines.push(`vector_topk: ${debugInfo.vector_topk.map(c => `${c.unit_id}(${c.score.toFixed(2)})`).join(', ')}`)
  }
  if (debugInfo.rrf_topk?.length) {
    lines.push(`rrf_topk: ${debugInfo.rrf_topk.map(c => `${c.unit_id}(${c.score.toFixed(4)})`).join(', ')}`)
  }
  return lines.join('\n')
}

async function copyDebugContext() {
  const text = buildDebugContext()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    setCopyFeedback('已复制')
  } catch {
    if (fallbackCopyText(text)) {
      setCopyFeedback('已复制')
    } else {
      setCopyFeedback('复制失败')
    }
  }
}

onBeforeUnmount(() => {
  if (copyFeedbackTimer) clearTimeout(copyFeedbackTimer)
})
</script>
