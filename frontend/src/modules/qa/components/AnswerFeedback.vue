<template>
  <section class="module-stack" aria-label="回答评价与纠错">
    <div class="row"><strong>回答帮助度</strong><div class="feedback-buttons">
      <button type="button" class="secondary-button" :disabled="pending" @click="send('answer_helpfulness', 'helpful')">有帮助</button>
      <button type="button" class="secondary-button" :disabled="pending" @click="send('answer_helpfulness', 'not_helpful')">没有帮助</button>
    </div></div>
    <details v-if="answered"><summary>提交事实纠错</summary><div class="module-stack">
      <label :for="`correction-${requestId}`">纠错说明</label>
      <textarea :id="`correction-${requestId}`" v-model="correction" class="input-area" maxlength="2000" :disabled="pending" placeholder="说明哪项事实有误及依据…" />
      <button type="button" class="secondary-button" :disabled="pending || !correction.trim()" @click="send('factual_correction', 'correction', correction)">提交纠错</button>
    </div></details>
    <details v-if="candidates.length && eventId"><summary>评价候选相关性</summary><div class="module-stack">
      <label :for="`candidate-${requestId}`">选择候选证据</label>
      <select :id="`candidate-${requestId}`" v-model="candidateId" :disabled="pending">
        <option value="">请选择候选证据</option>
        <option v-for="item in candidates" :key="item.id" :value="item.id">{{ item.label }}</option>
      </select>
      <div class="feedback-buttons"><button type="button" class="secondary-button" :disabled="pending || !candidateId" @click="send('candidate_relevance', 'relevant')">相关</button>
        <button type="button" class="secondary-button" :disabled="pending || !candidateId" @click="send('candidate_relevance', 'not_relevant')">不相关</button></div>
    </div></details>
    <label v-if="devMode" class="muted"><input v-model="testFeedback" type="checkbox" :disabled="pending" /> 验证反馈（单独标记）</label>
    <p v-if="pending" role="status" class="muted">正在保存反馈…</p>
    <p v-if="notice" role="status" class="notice">{{ notice }}</p>
    <p v-if="error" role="alert" class="error-message">{{ error }}</p>
    <p class="muted">反馈保持待复核状态。回答评价、候选相关性和事实纠错分别保存。</p>
  </section>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { errorMessage } from '../../../shared/http'
import { submitUserFeedback } from '../api'
import type { UserFeedbackRequest, UserFeedbackResponse } from '../types'
const props = withDefaults(defineProps<{ requestId: string; eventId?: string | null; answered: boolean; candidates?: { id: string; label: string }[] }>(), { eventId: null, candidates: () => [] })
const emit = defineEmits<{ recorded: [value: UserFeedbackResponse] }>()
const devMode = import.meta.env.DEV, testFeedback = ref(false)
const pending = ref(false), notice = ref(''), error = ref(''), correction = ref(''), candidateId = ref('')
let lastSignature = '', lastKey = ''
async function send(kind: UserFeedbackRequest['kind'], value: UserFeedbackRequest['value'], comment = '') {
  if (pending.value) return
  const payload = { request_id: props.requestId, event_id: props.eventId, candidate_id: kind === 'candidate_relevance' ? candidateId.value : null, kind, value, comment, origin: testFeedback.value ? 'automated_test' as const : 'user_submission' as const }
  const signature = JSON.stringify(payload)
  if (signature !== lastSignature) { lastSignature = signature; lastKey = crypto.randomUUID() }
  pending.value = true; notice.value = ''; error.value = ''
  try {
    const result = await submitUserFeedback({ ...payload, idempotency_key: lastKey })
    notice.value = `${result.replayed ? '该反馈已保存' : '反馈已保存'}，等待复核。反馈 ID：${result.feedback.id}`
    emit('recorded', result)
  } catch (cause) { error.value = errorMessage(cause) }
  finally { pending.value = false }
}
</script>
