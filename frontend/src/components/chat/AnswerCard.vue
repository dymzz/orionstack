<template>
  <section class="card answer-card">
    <div class="meta-row">
      <span class="badge">{{ responseStatus }}</span>
      <span class="trace-id">trace_id: {{ traceId }}</span>
    </div>
    <p class="answer-text">{{ answer }}</p>
    <div class="feedback-row">
      <span class="feedback-label">这条回答是否有帮助？</span>
      <div class="feedback-actions">
        <button
          class="ghost-button feedback-button"
          :class="{ 'feedback-button-active': selectedFeedback === 'up' }"
          :disabled="feedbackSubmitting"
          @click="$emit('feedback', 'up')"
        >
          👍 有帮助
        </button>
        <button
          class="ghost-button feedback-button"
          :class="{ 'feedback-button-active': selectedFeedback === 'down' }"
          :disabled="feedbackSubmitting"
          @click="$emit('feedback', 'down')"
        >
          👎 没帮助
        </button>
      </div>
    </div>
    <p v-if="feedbackMessage" class="feedback-message">{{ feedbackMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import type { FeedbackLabel } from '../../types/chat'

defineEmits<{
  (e: 'feedback', value: FeedbackLabel): void
}>()

defineProps<{
  answer: string
  responseStatus: string
  traceId: string
  feedbackSubmitting: boolean
  selectedFeedback: FeedbackLabel | null
  feedbackMessage: string
}>()
</script>
