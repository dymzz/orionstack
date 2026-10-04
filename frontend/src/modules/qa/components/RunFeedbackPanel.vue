<template>
  <section class="notice module-stack" aria-label="本次系统反馈">
    <div class="row"><strong>{{ callLabel }}</strong><button class="secondary-button" :disabled="refreshing" @click="refresh">{{ refreshing ? '核对中…' : '重新核对本次状态' }}</button></div>
    <p>{{ reasons[current.reason] ?? '本次状态需要进一步核对。' }}</p>
    <p v-if="current.audit_status === 'unavailable'" class="error-message">本次运行的审计记录未能保存，服务器暂时不能提供持久回执。</p>
    <p v-if="error" role="alert" class="error-message">{{ error }}</p>
    <dl class="facts">
      <dt>模式</dt><dd>{{ current.mode === 'knowledge' ? '资料问答' : '普通聊天' }}</dd>
      <dt>模型调用</dt><dd>{{ current.model_call.attempted === true ? '已发起' : current.model_call.attempted === false ? '未发起' : '未知' }}{{ current.model_call.model ? ` · ${current.model_call.model}` : '' }}</dd>
      <template v-if="current.mode === 'knowledge' && current.raw_candidate_count !== null"><dt>资料召回</dt><dd>{{ current.raw_candidate_count }} 个原始候选 · {{ current.final_candidate_count ?? '未知' }} 个当前可用候选</dd></template>
      <dt>请求 ID</dt><dd class="identifier">{{ current.request_id }}</dd>
      <dt>记录时间</dt><dd>{{ current.recorded_at }}</dd>
    </dl>
    <details><summary>回执原因与版本</summary>
      <p class="identifier">{{ current.reason }}{{ current.model_call.error_code ? ` · ${current.model_call.error_code}` : '' }}</p>
      <p v-if="current.retrieval_event_id" class="identifier">原始事件：{{ current.retrieval_event_id }}</p>
      <p class="identifier">Prompt：{{ current.runtime_versions.prompt_version ?? '未知' }}</p>
    </details>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { errorMessage } from '../../../shared/http'
import { getExecutionFeedback } from '../api'
import type { RunFeedback } from '../types'
const props = defineProps<{ feedback: RunFeedback }>()
const current = ref(props.feedback), refreshing = ref(false), error = ref('')
watch(() => props.feedback, value => { current.value = value; error.value = '' })
const callLabel = computed(() => {
  const call = current.value.model_call
  if (call.status === 'skipped') return '未调用 DeepSeek'
  if (call.status === 'succeeded') return 'DeepSeek 已返回'
  if (call.status === 'failed') return call.attempted ? 'DeepSeek 调用未完成有效回答' : '调用前检查未通过'
  return '模型调用状态未知'
})
const reasons: Record<string, string> = {
  answered: '资料回答已与当前可访问原文逐条核对。', general_response: '这是普通聊天回答，本次未检索企业资料，也没有企业原文核验。',
  no_raw_candidates: '当前授权范围没有召回资料，因此跳过模型调用。', processing_filtered_all: '原始召回已保存，但后处理没有保留可用候选，因此跳过模型调用。',
  sources_unavailable: '候选来源在调用前已不可访问或不再有效，因此跳过模型调用。', model_insufficient_evidence: '模型已处理候选资料，但没有给出足以作答的原文引用。',
  unverified_answer: '模型输出未通过引用或回答结构核验，未作为已核验答案返回。', source_changed: '模型调用后，引用来源的版本或访问范围发生变化，已停止返回该答案。',
  provider_failed: '模型服务调用失败，请根据本次回执核对后重试。', configuration_missing: '模型调用所需的服务端配置缺失，未完成回答。',
  retrieval_failed: '资料检索依赖未完成，本次没有进入回答模型调用。', audit_unavailable: '运行记录未能保存，本次请求以失败返回。',
}
async function refresh() {
  refreshing.value = true; error.value = ''
  try { current.value = (await getExecutionFeedback(current.value.request_id)).execution_feedback }
  catch (cause) { error.value = errorMessage(cause) }
  finally { refreshing.value = false }
}
</script>
