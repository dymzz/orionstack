<template>
  <section class="card document-library">
    <div class="document-library-head">
      <div>
        <h2>文档库</h2>
        <p class="document-library-subtitle">上传后的文档可在此选择问答范围或执行删除。</p>
      </div>
      <button class="ghost-button" :disabled="loading" @click="$emit('refresh')">
        {{ loading ? '刷新中...' : '刷新列表' }}
      </button>
    </div>

    <p class="document-scope-hint">
      {{
        selectedIds.length > 0
          ? `当前仅在 ${selectedIds.length} 份已选文档内检索。`
          : '当前未限定文档范围，将按全库检索。'
      }}
    </p>

    <p v-if="message" class="document-library-message">{{ message }}</p>
    <p v-if="loading && documents.length === 0" class="document-empty">文档列表加载中...</p>
    <p v-else-if="documents.length === 0" class="document-empty">尚未上传文档。</p>

    <ul v-else class="document-library-list">
      <li v-for="doc in documents" :key="doc.document_id" class="document-library-item">
        <label class="document-selection">
          <input
            type="checkbox"
            :checked="selectedIds.includes(doc.document_id)"
            :disabled="deletingId === doc.document_id"
            @change="toggleSelect(doc.document_id)"
          />
          <div>
            <strong>{{ doc.filename }}</strong>
            <p class="document-library-meta">{{ formatMeta(doc) }}</p>
          </div>
        </label>
        <button
          class="ghost-button document-delete-button"
          :disabled="deletingId.length > 0"
          @click="$emit('delete', doc.document_id)"
        >
          {{ deletingId === doc.document_id ? '删除中...' : '删除' }}
        </button>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import type { DocumentListItem } from '../../types/document'

const props = defineProps<{
  documents: DocumentListItem[]
  selectedIds: string[]
  loading: boolean
  message: string
  deletingId: string
}>()

const emit = defineEmits<{
  refresh: []
  delete: [value: string]
  'update:selectedIds': [value: string[]]
}>()

function toggleSelect(docId: string) {
  const next = props.selectedIds.includes(docId)
    ? props.selectedIds.filter((id) => id !== docId)
    : [...props.selectedIds, docId]
  emit('update:selectedIds', next)
}

function formatMeta(doc: DocumentListItem) {
  const createdAt = new Date(doc.created_at)
  const text = Number.isNaN(createdAt.getTime()) ? doc.created_at : createdAt.toLocaleString()
  return `上传时间：${text} · chunks：${doc.chunk_count} · text_length：${doc.text_length}`
}
</script>
