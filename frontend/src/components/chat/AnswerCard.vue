<template>
  <section class="card answer-card">
    <div class="meta-row">
      <span class="badge" :class="statusBadgeClass">{{ statusBadgeText }}</span>
      <span class="trace-id">trace_id: {{ traceId }}</span>
    </div>
    <div v-if="clarification?.clarification_required" class="clarification-panel">
      <p class="clarification-kicker">需要补充确认</p>
      <p class="clarification-question">{{ clarification.question }}</p>
      <p v-if="clarification.conflict_reason" class="clarification-reason">
        触发原因：{{ clarification.conflict_reason }}
      </p>
      <p v-if="answer" class="answer-text clarification-answer">{{ answer }}</p>
      <ul v-if="clarification.options.length > 0" class="clarification-option-list">
        <li v-for="option in clarification.options" :key="option.option_id" class="clarification-option">
          <button
            class="ghost-button clarification-option-button"
            type="button"
            :disabled="clarificationSubmitting"
            @click="$emit('clarification-select', option.label)"
          >
            {{ option.label }}
          </button>
        </li>
      </ul>
    </div>
    <p v-else class="answer-text">{{ answer }}</p>
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
import { computed } from 'vue'
import type { ClarificationInfo, FeedbackLabel, ResponseStatus } from '../../types/chat'

defineEmits<{
  (e: 'feedback', value: FeedbackLabel): void
  (e: 'clarification-select', value: string): void
}>()

const props = defineProps<{
  answer: string
  responseStatus: ResponseStatus
  traceId: string
  feedbackSubmitting: boolean
  clarificationSubmitting: boolean
  selectedFeedback: FeedbackLabel | null
  feedbackMessage: string
  clarification?: ClarificationInfo | null
}>()

const statusBadgeText = computed(() => {
  if (props.clarification?.clarification_required) {
    return '需要澄清'
  }

  switch (props.responseStatus) {
    case 'ok':
      return '正常回答'
    case 'refused':
      return '拒答'
    case 'fallback':
      return '需要更明确问题'
    case 'system_error':
      return '系统异常'
  }
})

const statusBadgeClass = computed(() => {
  if (props.clarification?.clarification_required) {
    return 'badge-status-clarification'
  }

  switch (props.responseStatus) {
    case 'ok':
      return 'badge-status-ok'
    case 'refused':
      return 'badge-status-refused'
    case 'fallback':
      return 'badge-status-fallback'
    case 'system_error':
      return 'badge-status-system'
  }
})
</script>
