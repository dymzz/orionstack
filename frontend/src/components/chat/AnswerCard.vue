<template>
  <section class="card answer-card">
    <div class="meta-row">
      <span class="badge" :class="statusBadgeClass">{{ statusBadgeText }}</span>
      <span class="trace-id">trace_id: {{ traceId }}</span>
    </div>
    <p class="answer-text">{{ answer }}</p>
    <DynamicQueryCard :result="dynamicQueryResult" />
    <div v-if="actionLinks && actionLinks.length > 0" class="action-links">
      <a
        v-for="link in actionLinks"
        :key="link.action_link_id"
        :href="link.url"
        target="_blank"
        rel="noopener noreferrer"
        class="action-link-button"
      >
        {{ link.label }} →
      </a>
    </div>
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
import type { ActionLinkItem, DynamicQueryResultItem, FeedbackLabel, ResponseStatus } from '../../types/chat'
import DynamicQueryCard from './DynamicQueryCard.vue'

defineEmits<{
  (e: 'feedback', value: FeedbackLabel): void
}>()

const props = defineProps<{
  answer: string
  responseStatus: ResponseStatus
  traceId: string
  feedbackSubmitting: boolean
  selectedFeedback: FeedbackLabel | null
  feedbackMessage: string
  actionLinks?: ActionLinkItem[]
  dynamicQueryResult?: DynamicQueryResultItem | null
}>()

const statusBadgeText = computed(() => {
  switch (props.responseStatus) {
    case 'ok': return '正常回答'
    case 'refused': return '拒答'
    case 'fallback': return '需要更明确问题'
    case 'system_error': return '系统异常'
  }
})

const statusBadgeClass = computed(() => {
  switch (props.responseStatus) {
    case 'ok': return 'badge-status-ok'
    case 'refused': return 'badge-status-refused'
    case 'fallback': return 'badge-status-fallback'
    case 'system_error': return 'badge-status-system'
  }
})
</script>
