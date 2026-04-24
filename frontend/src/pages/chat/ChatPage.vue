<template>
  <div>
    <ChatInput :loading="loading" @submit="handleSubmit" />

    <section v-if="errorMessage" class="error-box">
      {{ errorMessage }}
    </section>

    <ClarificationPanel
      v-if="response?.clarification?.clarification_required"
      :clarification="response.clarification"
      :answer="response.answer"
      :submitting="loading"
      @select="handleClarificationSelect"
    />

    <CitationList
      v-if="response && response.citations.length > 0"
      :citations="response.citations"
    />

    <AnswerCard
      v-if="response"
      :answer="response.answer"
      :response-status="response.response_status"
      :trace-id="response.trace_id"
      :feedback-submitting="feedbackSubmitting"
      :selected-feedback="selectedFeedback"
      :feedback-message="feedbackMessage"
      :action-links="response.action_links"
      :dynamic-query-result="response.dynamic_query_result"
      @feedback="handleFeedback"
    />

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
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import ChatInput from '../../components/chat/ChatInput.vue'
import AnswerCard from '../../components/chat/AnswerCard.vue'
import CitationList from '../../components/chat/CitationList.vue'
import ClarificationPanel from '../../components/chat/ClarificationPanel.vue'
import DocumentUpload from '../../components/chat/DocumentUpload.vue'
import DocumentLibrary from '../../components/chat/DocumentLibrary.vue'
import { askQuestion, submitFeedback } from '../../services/chat'
import { deleteDocument, listDocuments, uploadDocument } from '../../services/documents'
import type { ChatAskResponse, FeedbackLabel } from '../../types/chat'
import type { DocumentListItem } from '../../types/document'

const loading = ref(false)
const response = ref<ChatAskResponse | null>(null)
const errorMessage = ref('')
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

async function handleSubmit(rawQuery: string) {
  loading.value = true
  errorMessage.value = ''
  feedbackMessage.value = ''
  selectedFeedback.value = null
  lastSubmittedQuery.value = rawQuery
  try {
    response.value = await askQuestion(rawQuery, true, selectedDocumentIds.value)
  } catch (error) {
    response.value = null
    errorMessage.value = error instanceof Error ? error.message : '请求失败'
  } finally {
    loading.value = false
  }
}

async function handleClarificationSelect(optionLabel: string) {
  if (loading.value) return
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
    documentUploadMessage.value = error instanceof Error ? error.message : '文档上传失败'
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
  } catch (error) {
    documentLibraryMessage.value = error instanceof Error ? error.message : '文档列表加载失败'
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
    await refreshDocuments(`已删除：${documentId}`)
  } catch (error) {
    documentLibraryMessage.value = error instanceof Error ? error.message : '文档删除失败'
  } finally {
    deletingDocumentId.value = ''
  }
}

async function handleFeedback(label: FeedbackLabel) {
  if (!response.value || !lastSubmittedQuery.value || feedbackSubmitting.value) return
  feedbackSubmitting.value = true
  feedbackMessage.value = ''
  try {
    await submitFeedback({
      trace_id: response.value.trace_id,
      raw_query: lastSubmittedQuery.value,
      answer_text: response.value.answer,
      feedback_label: label,
      response_status: response.value.response_status,
      retrieved_chunk_ids: response.value.citations.map((c) => c.citation_id),
      normalized_query: response.value.debug_info?.normalized_query,
      router_used: response.value.debug_info?.router_used,
      route_result: response.value.debug_info?.route_result,
      fallback_reason: response.value.debug_info?.fallback_reason,
    })
    selectedFeedback.value = label
    feedbackMessage.value = label === 'up' ? '已记录：有帮助' : '已记录：没帮助'
  } catch (error) {
    feedbackMessage.value = error instanceof Error ? error.message : '反馈提交失败'
  } finally {
    feedbackSubmitting.value = false
  }
}

onMounted(() => {
  void refreshDocuments()
})
</script>
