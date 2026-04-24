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
  return [
    `trace_id: ${props.traceId}`,
    `response_status: ${props.responseStatus}`,
    `normalized_query: ${debugInfo.normalized_query}`,
    `route_result: ${debugInfo.route_result}`,
    `router_used: ${debugInfo.router_used}`,
    `route_confidence: ${formatOptionalNumber(debugInfo.route_confidence)}`,
    `retrieval_score: ${formatOptionalNumber(debugInfo.retrieval_score)}`,
    `planner_confidence: ${formatOptionalNumber(debugInfo.planner_confidence)}`,
    `domain_hint: ${formatOptionalText(debugInfo.domain_hint)}`,
    `fallback_reason: ${formatOptionalText(debugInfo.fallback_reason)}`,
    `clarification_required: ${props.clarificationRequired ? '是' : '否'}`,
    `clarification_question: ${props.clarificationQuestion ?? '无'}`,
    `lexical_terms: ${debugInfo.lexical_terms?.length ? debugInfo.lexical_terms.join(', ') : '无'}`,
    `retrieved_chunks: ${debugInfo.retrieved_chunks.length > 0 ? debugInfo.retrieved_chunks.join(', ') : '无'}`,
  ].join('\n')
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
