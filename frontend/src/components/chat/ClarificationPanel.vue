<template>
  <div v-if="clarification?.clarification_required" class="card clarification-panel">
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
          :disabled="submitting"
          @click="$emit('select', option.label)"
        >
          {{ option.label }}
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { ClarificationInfo } from '../../types/chat'

defineProps<{
  clarification?: ClarificationInfo | null
  answer?: string
  submitting: boolean
}>()

defineEmits<{
  select: [value: string]
}>()
</script>
