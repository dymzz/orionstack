<template>
  <section class="card record-panel">
    <div class="record-panel-head">
      <div>
        <h2>最近记录</h2>
        <p class="record-panel-subtitle">开发态最近 ask / feedback 记录，便于快速核对 trace 链路。</p>
      </div>
      <button class="ghost-button" :disabled="loading" @click="$emit('refresh')">
        {{ loading ? '刷新中...' : '刷新记录' }}
      </button>
    </div>

    <p v-if="message" class="record-panel-message">{{ message }}</p>

    <div class="record-section">
      <div class="record-section-head">
        <h3>最近问答</h3>
        <span class="record-count">{{ records.length }}</span>
      </div>
      <p v-if="records.length === 0" class="record-empty">暂无最近问答记录。</p>
      <ul v-else class="record-list">
        <li v-for="record in records" :key="record.trace_id" class="record-item">
          <div class="record-item-head">
            <span class="badge" :class="statusBadgeClass(record.response_status)">
              {{ record.response_status }}
            </span>
            <code class="record-trace">{{ record.trace_id }}</code>
          </div>
          <p class="record-query">{{ record.raw_query }}</p>
          <p class="record-meta">
            {{ formatTime(record.created_at) }}
            <span v-if="record.feedback_label"> · feedback: {{ record.feedback_label }}</span>
          </p>
          <p class="record-meta">
            chunks:
            {{ record.retrieved_chunk_ids.length > 0 ? record.retrieved_chunk_ids.join(', ') : '无' }}
          </p>
        </li>
      </ul>
    </div>

    <div class="record-section">
      <div class="record-section-head">
        <h3>最近反馈</h3>
        <span class="record-count">{{ feedbackItems.length }}</span>
      </div>
      <p v-if="feedbackItems.length === 0" class="record-empty">暂无最近反馈记录。</p>
      <ul v-else class="record-list">
        <li v-for="item in feedbackItems" :key="`${item.trace_id}-${item.created_at}`" class="record-item">
          <div class="record-item-head">
            <span class="badge record-feedback-badge">{{ item.feedback_label }}</span>
            <code class="record-trace">{{ item.trace_id }}</code>
          </div>
          <p class="record-query">{{ item.raw_query }}</p>
          <p class="record-meta">{{ formatTime(item.created_at) }} · response: {{ item.response_status }}</p>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { ChatRecordItem, FeedbackRecordItem } from '../../types/chat'

defineProps<{
  records: ChatRecordItem[]
  feedbackItems: FeedbackRecordItem[]
  loading: boolean
  message: string
}>()

defineEmits<{
  refresh: []
}>()

function formatTime(value: string) {
  const time = new Date(value)
  return Number.isNaN(time.getTime()) ? value : time.toLocaleString()
}

function statusBadgeClass(status: string) {
  if (status === 'ok') {
    return 'record-status-ok'
  }
  if (status === 'refused') {
    return 'record-status-refused'
  }
  if (status === 'fallback') {
    return 'record-status-fallback'
  }
  return 'record-status-system'
}
</script>
