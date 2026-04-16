<template>
  <div class="app-shell">
    <header class="app-header">
      <div>
        <h1>OrionStack Demo</h1>
        <p>最小可运行 FAQ / 知识问答闭环</p>
      </div>
      <button v-if="canDebug" class="ghost-button" @click="debugOpen = !debugOpen">
        {{ debugOpen ? '隐藏 Debug' : '显示 Debug' }}
      </button>
    </header>

    <main class="app-main">
      <DocumentUpload :uploading="documentUploading" :upload-message="documentUploadMessage" @upload="handleDocumentUpload" />

      <ChatInput :loading="loading" @submit="handleSubmit" />

      <section v-if="errorMessage" class="error-box">
        {{ errorMessage }}
      </section>

      <AnswerCard
        v-if="response"
        :answer="response.answer"
        :response-status="response.response_status"
        :trace-id="response.trace_id"
        :feedback-submitting="feedbackSubmitting"
        :selected-feedback="selectedFeedback"
        :feedback-message="feedbackMessage"
        @feedback="handleFeedback"
      />

      <CitationList
        v-if="response && response.citations.length > 0"
        :citations="response.citations"
      />

      <section v-if="debugOpen && response?.debug_info" class="card debug-panel">
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
            <dd>{{ response.trace_id }}</dd>
          </div>
          <div class="debug-item">
            <dt>response_status</dt>
            <dd>{{ response.response_status }}</dd>
          </div>
          <div class="debug-item">
            <dt>normalized_query</dt>
            <dd>{{ response.debug_info.normalized_query }}</dd>
          </div>
          <div class="debug-item">
            <dt>route_result</dt>
            <dd>{{ response.debug_info.route_result }}</dd>
          </div>
          <div class="debug-item">
            <dt>router_used</dt>
            <dd>{{ response.debug_info.router_used }}</dd>
          </div>
          <div class="debug-item">
            <dt>route_confidence</dt>
            <dd>{{ formatOptionalNumber(response.debug_info.route_confidence) }}</dd>
          </div>
          <div class="debug-item">
            <dt>retrieval_score</dt>
            <dd>{{ formatOptionalNumber(response.debug_info.retrieval_score) }}</dd>
          </div>
          <div class="debug-item debug-item-wide">
            <dt>fallback_reason</dt>
            <dd>{{ formatOptionalText(response.debug_info.fallback_reason) }}</dd>
          </div>
          <div class="debug-item debug-item-wide">
            <dt>retrieved_chunks</dt>
            <dd>
              <ul v-if="response.debug_info.retrieved_chunks.length > 0" class="debug-list">
                <li v-for="chunkId in response.debug_info.retrieved_chunks" :key="chunkId">
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
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount } from 'vue'
import ChatInput from '../../components/chat/ChatInput.vue'
import AnswerCard from '../../components/chat/AnswerCard.vue'
import CitationList from '../../components/chat/CitationList.vue'
import DocumentUpload from '../../components/chat/DocumentUpload.vue'
import { askQuestion, submitFeedback } from '../../services/chat'
import { uploadDocument } from '../../services/documents'
import type { ChatAskResponse, FeedbackLabel } from '../../types/chat'

const canDebug = import.meta.env.MODE !== 'production'
const loading = ref(false)
const debugOpen = ref(canDebug)
const response = ref<ChatAskResponse | null>(null)
const errorMessage = ref('')
const copyFeedback = ref('')
const feedbackSubmitting = ref(false)
const selectedFeedback = ref<FeedbackLabel | null>(null)
const feedbackMessage = ref('')
const lastSubmittedQuery = ref('')
const documentUploading = ref(false)
const documentUploadMessage = ref('')

const debugInfoJson = computed(() => {
  if (!response.value?.debug_info) {
    return ''
  }

  return JSON.stringify(response.value.debug_info, null, 2)
})

let copyFeedbackTimer: ReturnType<typeof setTimeout> | null = null

async function handleSubmit(rawQuery: string) {
  loading.value = true
  errorMessage.value = ''
  feedbackMessage.value = ''
  selectedFeedback.value = null
  lastSubmittedQuery.value = rawQuery
  try {
    response.value = await askQuestion(rawQuery, canDebug)
  } catch (error) {
    response.value = null
    const message = error instanceof Error ? error.message : '请求失败'
    errorMessage.value = message
  } finally {
    loading.value = false
  }
}

async function handleDocumentUpload(file: File) {
  documentUploading.value = true
  documentUploadMessage.value = ''

  try {
    const result = await uploadDocument(file)
    documentUploadMessage.value = `已上传：${result.filename}（document_id: ${result.document_id}，text_length: ${result.text_length}，chunks: ${result.chunk_count}）`
  } catch (error) {
    const message = error instanceof Error ? error.message : '文档上传失败'
    documentUploadMessage.value = message
  } finally {
    documentUploading.value = false
  }
}

async function handleFeedback(label: FeedbackLabel) {
  if (!response.value || !lastSubmittedQuery.value || feedbackSubmitting.value) {
    return
  }

  feedbackSubmitting.value = true
  feedbackMessage.value = ''

  try {
    await submitFeedback({
      trace_id: response.value.trace_id,
      raw_query: lastSubmittedQuery.value,
      answer_text: response.value.answer,
      feedback_label: label,
      response_status: response.value.response_status,
      retrieved_chunk_ids: response.value.citations.map((citation) => citation.citation_id),
      normalized_query: response.value.debug_info?.normalized_query,
      router_used: response.value.debug_info?.router_used,
      route_result: response.value.debug_info?.route_result,
      fallback_reason: response.value.debug_info?.fallback_reason,
    })
    selectedFeedback.value = label
    feedbackMessage.value = label === 'up' ? '已记录：有帮助' : '已记录：没帮助'
  } catch (error) {
    const message = error instanceof Error ? error.message : '反馈提交失败'
    feedbackMessage.value = message
  } finally {
    feedbackSubmitting.value = false
  }
}

function formatOptionalNumber(value?: number | null) {
  if (value === undefined || value === null) {
    return '无'
  }

  return value.toFixed(2)
}

function formatOptionalText(value?: string | null) {
  return value && value.trim() ? value : '无'
}

function buildDebugContext() {
  if (!response.value?.debug_info) {
    return ''
  }

  const { debug_info: debugInfo } = response.value

  return [
    `trace_id: ${response.value.trace_id}`,
    `response_status: ${response.value.response_status}`,
    `normalized_query: ${debugInfo.normalized_query}`,
    `route_result: ${debugInfo.route_result}`,
    `router_used: ${debugInfo.router_used}`,
    `route_confidence: ${formatOptionalNumber(debugInfo.route_confidence)}`,
    `retrieval_score: ${formatOptionalNumber(debugInfo.retrieval_score)}`,
    `fallback_reason: ${formatOptionalText(debugInfo.fallback_reason)}`,
    `retrieved_chunks: ${debugInfo.retrieved_chunks.length > 0 ? debugInfo.retrieved_chunks.join(', ') : '无'}`,
  ].join('\n')
}

function setCopyFeedback(message: string) {
  copyFeedback.value = message

  if (copyFeedbackTimer) {
    clearTimeout(copyFeedbackTimer)
  }

  copyFeedbackTimer = setTimeout(() => {
    copyFeedback.value = ''
  }, 2000)
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

async function copyDebugContext() {
  const debugContext = buildDebugContext()
  if (!debugContext) {
    return
  }

  try {
    await navigator.clipboard.writeText(debugContext)
    setCopyFeedback('已复制')
  } catch {
    if (fallbackCopyText(debugContext)) {
      setCopyFeedback('已复制')
      return
    }

    setCopyFeedback('复制失败')
  }
}

onBeforeUnmount(() => {
  if (copyFeedbackTimer) {
    clearTimeout(copyFeedbackTimer)
  }
})
</script>
