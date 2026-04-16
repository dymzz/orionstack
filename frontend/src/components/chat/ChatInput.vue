<template>
  <section class="card">
    <label class="label" for="chat-input">请输入问题</label>
    <textarea
      id="chat-input"
      v-model="draft"
      class="input-area"
      rows="4"
      placeholder="例如：如何上传文档？"
      @keydown.ctrl.enter.prevent="submit"
    />
    <div class="actions">
      <button class="primary-button" :disabled="loading || !draft.trim()" @click="submit">
        {{ loading ? '发送中...' : '提交问题' }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ loading: boolean }>()
const emit = defineEmits<{ (e: 'submit', value: string): void }>()
const draft = ref('如何上传文档？')

function submit() {
  const value = draft.value.trim()
  if (!value || props.loading) return
  emit('submit', value)
}
</script>
