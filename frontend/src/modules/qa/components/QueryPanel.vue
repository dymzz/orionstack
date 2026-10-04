<template>
  <section class="card module-stack">
    <div class="row"><h2>工作台</h2><button class="secondary-button" :disabled="loading" @click="clear">新对话</button></div>
    <p class="muted">输入消息即可，系统会判断是否查询资料、直接回答或记录反馈。资料回答附原文引用。</p>
    <p v-if="historyError" role="alert" class="error-message">{{ historyError }}</p>
    <p v-if="accessError" role="alert" class="error-message">{{ accessError }}</p>
    <div ref="thread" class="chat-thread" role="log" aria-label="工作台对话" aria-live="polite">
      <div v-if="!turns.length" class="chat-welcome">今天需要处理什么？<p>可以提问、聊天，或告诉我上一条回答需要怎样改正。</p></div>
      <article v-for="turn in turns" :key="turn.id" class="chat-turn">
        <span class="badge">{{ turn.output?.kind === 'general_chat' ? '通用回答' : turn.output?.kind === 'knowledge' ? '资料问答' : turn.output?.kind === 'system' ? '系统回执' : turn.output?.kind === 'failure' ? '处理失败' : '自动处理' }}</span>
        <p class="chat-question">{{ turn.question }}</p>
        <p v-if="turn.pending" class="notice" role="status">{{ turn.status || '正在处理…' }}</p>
        <p v-if="turn.steps.length" class="muted">{{ turn.steps.join(' → ') }}</p>
        <p v-if="turn.pending && turn.draft" class="quote">{{ turn.draft }}</p>
        <p v-if="turn.output?.kind === 'system'" class="quote">{{ turn.output.message }}</p>
        <p v-if="turn.output?.feedback" class="notice">反馈已记录，等待复核；不会直接改变原始召回或训练标签。</p>
        <p v-if="turn.withheld" class="notice">来源或权限已变化，此轮原文和回答暂不展示。</p>
        <button v-if="!turn.pending && !turn.output && !turn.withheld" :disabled="loading" class="secondary-button" @click="retry(turn)">重试此消息</button>
        <p v-if="turn.error" role="alert" class="error-message">{{ turn.error }}</p>
        <div v-if="turn.response" class="chat-answer module-stack">
          <div class="row"><h3>{{ turn.response.status === 'answered' ? '回答' : '证据不足' }}</h3><span class="badge">{{ turn.response.validation === 'source_and_quote_checked' ? '引用与原文对应' : turn.response.raw_candidate_count === 0 ? '未找到可用资料' : '证据不足以作答' }}</span></div>
          <p class="quote">{{ turn.response.answer }}</p>
          <details v-if="turn.response.citations.length"><summary>引用原文（{{ turn.response.citations.length }}）</summary>
            <div v-for="citation in turn.response.citations" :key="citation.evidence_id + citation.quote">
              <blockquote class="quote">{{ citation.quote }}</blockquote><p class="identifier">{{ citation.source.source_locator }}</p>
            </div>
          </details>
          <TraceLinks :request-id="turn.response.request_id" :event-id="turn.response.retrieval_event_id" :run-id="turn.response.processing_run_id" />
          <p class="muted">召回 {{ turn.response.raw_candidate_count }} 个候选 · 保留 {{ turn.response.final_candidate_count }} 个候选{{ turn.response.processing_status === 'raw_fallback' ? ' · 已回退原始候选' : '' }}</p>
          <details v-if="turn.response.evidence_bundle"><summary>证据与来源链（{{ turn.response.evidence_bundle.items.length }}）</summary><EvidencePanel :items="turn.response.evidence_bundle.items" /></details>
          <p class="muted">冲突与完整覆盖：尚未检查</p>
        </div>
        <div v-if="turn.general" class="chat-answer module-stack"><div class="row"><h3>通用回答</h3><span class="badge">未检索企业资料</span></div><p class="quote">{{ turn.general.answer }}</p><p class="muted">普通聊天回答不具有企业原文引用或来源链核验。</p><TraceLinks :request-id="turn.general.request_id" /></div>
        <details v-if="turn.feedback && turn.output?.kind !== 'system'"><summary>回答评价与纠错</summary><AnswerFeedback :request-id="turn.feedback.request_id" :event-id="turn.feedback.retrieval_event_id" :answered="turn.feedback.outcome === 'answered'" :candidates="(turn.response?.evidence_bundle?.items ?? []).map(item => ({ id: item.evidence_id, label: `候选 ${item.raw_rank ?? '—'} · ${item.source.source_locator}` }))" /></details>
        <details v-if="turn.feedback"><summary>本次系统反馈</summary><RunFeedbackPanel :feedback="turn.feedback" /></details>
        <details v-if="turn.output?.routing_call"><summary>本次处理方式</summary><p class="muted">路由判断调用：{{ turn.output.routing_call.provider }} · {{ turn.output.routing_call.status }}</p><p v-if="turn.output.route" class="muted">{{ turn.output.route.needs_retrieval ? '查询资料' : turn.output.route.is_system_status ? '读取运行回执' : '直接处理' }}{{ turn.output.route.is_feedback ? ' · 记录反馈' : '' }}</p></details>
        <p v-if="!turn.feedback && !turn.pending" class="muted">服务器没有返回本次模型调用回执，当前无法确认调用状态。</p>
      </article>
    </div>
    <form class="chat-composer" @submit.prevent="submit">
      <label for="core-question">消息</label>
      <textarea id="core-question" v-model="question" class="input-area" :disabled="loading" placeholder="输入问题…" maxlength="4000" @keydown.ctrl.enter.prevent="submit" @keydown.meta.enter.prevent="submit" />
      <div class="row"><span class="muted">会话由服务端保存，刷新后可继续。</span><button class="primary-button" type="submit" :disabled="loading || !question.trim() || !permissions?.query">{{ loading ? '处理中…' : '发送' }}</button></div>
    </form>
  </section>
</template>
<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useAuthState } from '../../account'
import { TraceLinks } from '../../logs'
import { useQuery } from '../state'
import EvidencePanel from './EvidencePanel.vue'
import RunFeedbackPanel from './RunFeedbackPanel.vue'
import AnswerFeedback from './AnswerFeedback.vue'
const { permissions, accessError } = useAuthState()
const { question, loading, turns, historyError, submit, clear, retry } = useQuery()
const thread = ref<HTMLElement | null>(null)
watch(() => [turns.value.length, loading.value], async () => { await nextTick(); thread.value?.scrollTo({ top: thread.value.scrollHeight, behavior: 'smooth' }) })
</script>
