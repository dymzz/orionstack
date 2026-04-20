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

      <RecordList
        v-if="canDebug"
        :records="chatRecords"
        :feedback-items="feedbackRecords"
        :loading="recordPanelLoading"
        :message="recordPanelMessage"
        @refresh="refreshRecordPanel()"
      />

      <section class="card document-library">
        <div class="document-library-head">
          <div>
            <h2>文档库</h2>
            <p class="document-library-subtitle">上传后的文档可在此选择问答范围或执行删除。</p>
          </div>
          <button class="ghost-button" :disabled="documentsLoading" @click="refreshDocuments()">
            {{ documentsLoading ? '刷新中...' : '刷新列表' }}
          </button>
        </div>

        <p class="document-scope-hint">
          {{
            selectedDocumentIds.length > 0
              ? `当前仅在 ${selectedDocumentIds.length} 份已选文档内检索。`
              : '当前未限定文档范围，将按全库检索。'
          }}
        </p>

        <p v-if="documentLibraryMessage" class="document-library-message">{{ documentLibraryMessage }}</p>
        <p v-if="documentsLoading && documents.length === 0" class="document-empty">文档列表加载中...</p>
        <p v-else-if="documents.length === 0" class="document-empty">尚未上传文档。</p>

        <ul v-else class="document-library-list">
          <li v-for="document in documents" :key="document.document_id" class="document-library-item">
            <label class="document-selection">
              <input
                v-model="selectedDocumentIds"
                type="checkbox"
                :value="document.document_id"
                :disabled="deletingDocumentId === document.document_id"
              />
              <div>
                <strong>{{ document.filename }}</strong>
                <p class="document-library-meta">
                  {{ formatDocumentMeta(document) }}
                </p>
              </div>
            </label>

            <button
              class="ghost-button document-delete-button"
              :disabled="deletingDocumentId.length > 0"
              @click="handleDocumentDelete(document.document_id)"
            >
              {{ deletingDocumentId === document.document_id ? '删除中...' : '删除' }}
            </button>
          </li>
        </ul>
      </section>

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
        :clarification-submitting="loading"
        :selected-feedback="selectedFeedback"
        :feedback-message="feedbackMessage"
        :clarification="response.clarification"
        @feedback="handleFeedback"
        @clarification-select="handleClarificationSelect"
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
          <div class="debug-item">
            <dt>planner_confidence</dt>
            <dd>{{ formatOptionalNumber(response.debug_info.planner_confidence) }}</dd>
          </div>
          <div class="debug-item">
            <dt>domain_hint</dt>
            <dd>{{ formatOptionalText(response.debug_info.domain_hint) }}</dd>
          </div>
          <div class="debug-item debug-item-wide">
            <dt>fallback_reason</dt>
            <dd>{{ formatOptionalText(response.debug_info.fallback_reason) }}</dd>
          </div>
          <div class="debug-item debug-item-wide">
            <dt>clarification_required</dt>
            <dd>{{ response.clarification?.clarification_required ? '是' : '否' }}</dd>
          </div>
          <div
            v-if="response.clarification?.clarification_required"
            class="debug-item debug-item-wide"
          >
            <dt>clarification_question</dt>
            <dd>{{ response.clarification.question }}</dd>
          </div>
          <div class="debug-item debug-item-wide">
            <dt>lexical_terms</dt>
            <dd>
              <ul
                v-if="response.debug_info.lexical_terms && response.debug_info.lexical_terms.length > 0"
                class="debug-list"
              >
                <li v-for="term in response.debug_info.lexical_terms" :key="term">
                  <code>{{ term }}</code>
                </li>
              </ul>
              <span v-else class="debug-empty">无</span>
            </dd>
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
import { ref, computed, onBeforeUnmount, onMounted } from 'vue'
import ChatInput from '../../components/chat/ChatInput.vue'
import AnswerCard from '../../components/chat/AnswerCard.vue'
import CitationList from '../../components/chat/CitationList.vue'
import DocumentUpload from '../../components/chat/DocumentUpload.vue'
import RecordList from '../../components/chat/RecordList.vue'
import { askQuestion, listChatRecords, listFeedbackRecords, submitFeedback } from '../../services/chat'
import { deleteDocument, listDocuments, uploadDocument } from '../../services/documents'
import type { ChatAskResponse, ChatRecordItem, FeedbackLabel, FeedbackRecordItem } from '../../types/chat'
import type { DocumentListItem } from '../../types/document'

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
const documents = ref<DocumentListItem[]>([])
const documentsLoading = ref(false)
const documentLibraryMessage = ref('')
const deletingDocumentId = ref('')
const selectedDocumentIds = ref<string[]>([])
const chatRecords = ref<ChatRecordItem[]>([])
const feedbackRecords = ref<FeedbackRecordItem[]>([])
const recordPanelLoading = ref(false)
const recordPanelMessage = ref('')

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
    response.value = await askQuestion(rawQuery, canDebug, selectedDocumentIds.value)
    if (canDebug) {
      await refreshRecordPanel()
    }
  } catch (error) {
    response.value = null
    const message = error instanceof Error ? error.message : '请求失败'
    errorMessage.value = message
  } finally {
    loading.value = false
  }
}

async function handleClarificationSelect(optionLabel: string) {
  if (loading.value) {
    return
  }

  await handleSubmit(optionLabel)
}

async function handleDocumentUpload(file: File) {
  documentUploading.value = true
  documentUploadMessage.value = ''

  try {
    const result = await uploadDocument(file)
    documentUploadMessage.value = `已上传：${result.filename}（document_id: ${result.document_id}，text_length: ${result.text_length}，chunks: ${result.chunk_count}）`
    await refreshDocuments('文档列表已更新。')
  } catch (error) {
    const message = error instanceof Error ? error.message : '文档上传失败'
    documentUploadMessage.value = message
  } finally {
    documentUploading.value = false
  }
}

async function refreshDocuments(successMessage = '') {
  documentsLoading.value = true
  if (!successMessage) {
    documentLibraryMessage.value = ''
  }

  try {
    const result = await listDocuments()
    documents.value = result.items
    selectedDocumentIds.value = selectedDocumentIds.value.filter((documentId) =>
      result.items.some((document) => document.document_id === documentId),
    )
    if (successMessage) {
      documentLibraryMessage.value = successMessage
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '文档列表加载失败'
    documentLibraryMessage.value = message
  } finally {
    documentsLoading.value = false
  }
}

async function refreshRecordPanel(successMessage = '') {
  if (!canDebug) {
    return
  }

  recordPanelLoading.value = true
  if (!successMessage) {
    recordPanelMessage.value = ''
  }

  try {
    const [recordsResult, feedbackResult] = await Promise.all([
      listChatRecords(20),
      listFeedbackRecords(20),
    ])
    chatRecords.value = recordsResult.items
    feedbackRecords.value = feedbackResult.items
    if (successMessage) {
      recordPanelMessage.value = successMessage
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '最近记录加载失败'
    recordPanelMessage.value = message
  } finally {
    recordPanelLoading.value = false
  }
}

async function handleDocumentDelete(documentId: string) {
  if (deletingDocumentId.value) {
    return
  }

  deletingDocumentId.value = documentId
  documentLibraryMessage.value = ''

  try {
    const result = await deleteDocument(documentId)
    selectedDocumentIds.value = selectedDocumentIds.value.filter((item) => item !== documentId)
    await refreshDocuments(`已删除：${result.document_id}`)
  } catch (error) {
    const message = error instanceof Error ? error.message : '文档删除失败'
    documentLibraryMessage.value = message
  } finally {
    deletingDocumentId.value = ''
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
    await refreshRecordPanel('最近记录已刷新。')
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

function formatDocumentMeta(document: DocumentListItem) {
  const createdAt = new Date(document.created_at)
  const createdAtText = Number.isNaN(createdAt.getTime()) ? document.created_at : createdAt.toLocaleString()
  return `上传时间：${createdAtText} · chunks：${document.chunk_count} · text_length：${document.text_length}`
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
    `planner_confidence: ${formatOptionalNumber(debugInfo.planner_confidence)}`,
    `domain_hint: ${formatOptionalText(debugInfo.domain_hint)}`,
    `fallback_reason: ${formatOptionalText(debugInfo.fallback_reason)}`,
    `clarification_required: ${response.value.clarification?.clarification_required ? '是' : '否'}`,
    `clarification_question: ${response.value.clarification?.question ?? '无'}`,
    `lexical_terms: ${
      debugInfo.lexical_terms && debugInfo.lexical_terms.length > 0
        ? debugInfo.lexical_terms.join(', ')
        : '无'
    }`,
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

onMounted(() => {
  void refreshDocuments()
  void refreshRecordPanel()
})
</script>
