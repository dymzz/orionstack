<template>
  <div v-if="canUseWorkspace" class="chat-page">
    <div class="chat-history" ref="historyRef">
      <div v-if="turns.length === 0" class="chat-empty">
        <p class="chat-empty-hint">输入问题开始对话</p>
      </div>
      <div v-for="turn in turns" :key="turn.id" class="chat-turn">
        <div class="chat-turn-query">
          <span class="chat-turn-avatar chat-turn-avatar--user">Q</span>
          <div class="chat-turn-bubble chat-turn-bubble--user">{{ turn.query }}</div>
        </div>
        <div v-if="turn.error" class="chat-turn-error">{{ turn.error }}</div>
        <div v-if="turn.response" class="chat-turn-response">
          <span class="chat-turn-avatar chat-turn-avatar--bot">A</span>
          <div class="chat-turn-bubble chat-turn-bubble--bot">
            <AnswerCard
              :answer="turn.response.answer"
              :response-status="turn.response.response_status"
              :trace-id="turn.response.trace_id"
              :feedback-submitting="feedbackSubmitting && feedbackTraceId === turn.response.trace_id"
              :selected-feedback="feedbackTraceId === turn.response.trace_id ? selectedFeedback : null"
              :feedback-message="feedbackTraceId === turn.response.trace_id ? feedbackMessage : ''"
              :action-links="turn.response.action_links"
              :dynamic-query-result="turn.response.dynamic_query_result"
              @feedback="(label) => handleFeedback(turn, label)"
            />
            <ClarificationPanel
              v-if="turn.response.clarification?.clarification_required"
              :clarification="turn.response.clarification"
              :answer="turn.response.answer"
              :submitting="loading"
              @select="(label) => handleClarificationSelect(label)"
            />
            <CitationList
              v-if="turn.response.citations.length > 0"
              :citations="turn.response.citations"
            />
          </div>
        </div>
      </div>
      <div v-if="loading" class="chat-turn">
        <div class="chat-turn-response">
          <span class="chat-turn-avatar chat-turn-avatar--bot">A</span>
          <div class="chat-turn-bubble chat-turn-bubble--bot chat-turn-bubble--loading">
            思考中...
          </div>
        </div>
      </div>
    </div>

    <ChatInput :loading="loading" @submit="handleSubmit" />

    <DocumentUpload :uploading="documentUploading" :upload-message="documentUploadMessage" @upload="handleDocumentUpload" />

    <DocumentLibrary
      :documents="documents"
      :selected-ids="selectedDocumentIds"
      :loading="documentsLoading"
      :message="documentLibraryMessage"
      :deleting-id="deletingDocumentId"
      @refresh="refreshDocuments()"
      @delete="handleDocumentDelete"
      @update:selected-ids="selectedDocumentIds = $event"
    />
  </div>
  <section v-else class="card">
    <h2>当前账号权限不足</h2>
    <p>此页面的问答和文档维护需要管理员权限，请使用管理员账号登录。</p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, nextTick, watch } from 'vue'
import ChatInput from '../../components/chat/ChatInput.vue'
import AnswerCard from '../../components/chat/AnswerCard.vue'
import CitationList from '../../components/chat/CitationList.vue'
import ClarificationPanel from '../../components/chat/ClarificationPanel.vue'
import DocumentUpload from '../../components/chat/DocumentUpload.vue'
import DocumentLibrary from '../../components/chat/DocumentLibrary.vue'
import { askQuestion, submitFeedback } from '../../services/chat'
import { deleteDocument, listDocuments, uploadDocument } from '../../services/documents'
import { useAuthState } from '../../services/auth'
import { useChatHistory } from '../../composables/useChatHistory'
import { useToast } from '../../composables/useToast'
import type { FeedbackLabel } from '../../types/chat'
import type { DocumentListItem } from '../../types/document'

const { turns, addTurn, clearHistory } = useChatHistory()
const { currentRole } = useAuthState()
const canUseWorkspace = computed(() => currentRole.value === 'admin')
const { error: showError, success: showSuccess } = useToast()

const loading = ref(false)
const feedbackSubmitting = ref(false)
const feedbackTraceId = ref('')
const selectedFeedback = ref<FeedbackLabel | null>(null)
const feedbackMessage = ref('')
const documentUploading = ref(false)
const documentUploadMessage = ref('')
const documents = ref<DocumentListItem[]>([])
const documentsLoading = ref(false)
const documentLibraryMessage = ref('')
const deletingDocumentId = ref('')
const selectedDocumentIds = ref<string[]>([])
const historyRef = ref<HTMLElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    if (historyRef.value) {
      historyRef.value.scrollTop = historyRef.value.scrollHeight
    }
  })
}

watch(turns, () => {
  scrollToBottom()
}, { deep: true })

async function handleSubmit(rawQuery: string) {
  loading.value = true
  try {
    const response = await askQuestion(rawQuery, true, selectedDocumentIds.value)
    addTurn(rawQuery, response)
  } catch (err) {
    const message = err instanceof Error ? err.message : '请求失败'
    addTurn(rawQuery, null, message)
    showError(message)
  } finally {
    loading.value = false
  }
}

async function handleClarificationSelect(optionLabel: string) {
  await handleSubmit(optionLabel)
}

async function handleDocumentUpload(file: File) {
  documentUploading.value = true
  documentUploadMessage.value = ''
  try {
    const result = await uploadDocument(file)
    documentUploadMessage.value = `已上传：${result.filename}（document_id: ${result.document_id}，text_length: ${result.text_length}，chunks: ${result.chunk_count}）`
    showSuccess('文档上传成功')
    await refreshDocuments('文档列表已更新。')
  } catch (err) {
    const message = err instanceof Error ? err.message : '文档上传失败'
    documentUploadMessage.value = message
    showError(message)
  } finally {
    documentUploading.value = false
  }
}

async function refreshDocuments(successMessage = '') {
  documentsLoading.value = true
  if (!successMessage) documentLibraryMessage.value = ''
  try {
    const result = await listDocuments()
    documents.value = result.items
    selectedDocumentIds.value = selectedDocumentIds.value.filter((id) =>
      result.items.some((d) => d.document_id === id),
    )
    if (successMessage) documentLibraryMessage.value = successMessage
  } catch (err) {
    const message = err instanceof Error ? err.message : '文档列表加载失败'
    documentLibraryMessage.value = message
    showError(message)
  } finally {
    documentsLoading.value = false
  }
}

async function handleDocumentDelete(documentId: string) {
  if (deletingDocumentId.value) return
  deletingDocumentId.value = documentId
  documentLibraryMessage.value = ''
  try {
    await deleteDocument(documentId)
    selectedDocumentIds.value = selectedDocumentIds.value.filter((id) => id !== documentId)
    showSuccess('文档已删除')
    await refreshDocuments(`已删除：${documentId}`)
  } catch (err) {
    const message = err instanceof Error ? err.message : '文档删除失败'
    documentLibraryMessage.value = message
    showError(message)
  } finally {
    deletingDocumentId.value = ''
  }
}

async function handleFeedback(turn: { response: { trace_id: string } | null; query: string }, label: FeedbackLabel) {
  if (!turn.response || feedbackSubmitting.value) return
  feedbackSubmitting.value = true
  feedbackTraceId.value = turn.response.trace_id
  feedbackMessage.value = ''
  try {
    await submitFeedback({
      trace_id: turn.response.trace_id,
      raw_query: turn.query,
      answer_text: turn.response.answer,
      feedback_label: label,
      response_status: turn.response.response_status,
      retrieved_chunk_ids: turn.response.citations.map((c) => c.citation_id),
    })
    selectedFeedback.value = label
    feedbackMessage.value = label === 'up' ? '已记录：有帮助' : '已记录：没帮助'
    showSuccess(feedbackMessage.value)
  } catch (err) {
    feedbackMessage.value = err instanceof Error ? err.message : '反馈提交失败'
    showError(feedbackMessage.value)
  } finally {
    feedbackSubmitting.value = false
  }
}

onMounted(() => {
  if (canUseWorkspace.value) void refreshDocuments()
})
</script>

<style scoped>
.chat-page {
  max-width: 48rem;
  margin: 0 auto;
  padding: 0 1rem;
}

.chat-history {
  min-height: 12rem;
  max-height: 36rem;
  overflow-y: auto;
  padding: 1rem 0;
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 1rem;
}

.chat-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 10rem;
}

.chat-empty-hint {
  color: #9ca3af;
  font-size: 0.875rem;
}

.chat-turn {
  margin-bottom: 1.5rem;
}

.chat-turn-query,
.chat-turn-response {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.chat-turn-avatar {
  flex-shrink: 0;
  width: 1.75rem;
  height: 1.75rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
}

.chat-turn-avatar--user {
  background: #3b82f6;
  color: white;
}

.chat-turn-avatar--bot {
  background: #10b981;
  color: white;
}

.chat-turn-bubble {
  max-width: 36rem;
  font-size: 0.875rem;
  line-height: 1.5;
}

.chat-turn-bubble--user {
  background: #eff6ff;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  color: #1e40af;
}

.chat-turn-bubble--bot {
  padding: 0.25rem 0;
}

.chat-turn-bubble--loading {
  color: #9ca3af;
  font-style: italic;
}

.chat-turn-error {
  margin-left: 2.25rem;
  color: #dc2626;
  font-size: 0.8125rem;
  background: #fef2f2;
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  border: 1px solid #fecaca;
}
</style>
