<template>
  <section class="card">
    <label class="label" for="document-upload">上传文档</label>
    <input
      id="document-upload"
      class="file-input"
      type="file"
      accept=".txt,.md,.pdf,.docx"
      @change="handleFileChange"
    />
    <p v-if="selectedFile" class="upload-meta">已选择：{{ selectedFile.name }}</p>
    <div class="actions">
      <button class="primary-button" :disabled="uploading || !selectedFile" @click="submit">
        {{ uploading ? '上传中...' : '上传文档' }}
      </button>
    </div>
    <p v-if="uploadMessage" class="upload-message">{{ uploadMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  uploading: boolean
  uploadMessage: string
}>()

const emit = defineEmits<{
  (e: 'upload', file: File): void
}>()

const selectedFile = ref<File | null>(null)

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  selectedFile.value = target.files?.[0] ?? null
}

function submit() {
  if (!selectedFile.value || props.uploading) {
    return
  }

  emit('upload', selectedFile.value)
}
</script>
