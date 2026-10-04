<template>
  <section class="module-stack" aria-label="运行审计详情">
    <div class="row"><h3>本次运行</h3><span class="badge">{{ audit.run.mode === 'knowledge' ? '资料问答' : '普通聊天' }}</span></div>
    <p class="identifier">{{ audit.run.request_id }} · {{ audit.run.created_at }}</p>
    <RunFeedbackPanel :feedback="audit.run.execution_feedback" />
    <p v-if="audit.content_access === 'withheld'" class="notice">当前来源或访问范围已经变化，历史正文已隐藏。原始审计记录仍然保留。</p>
    <template v-else>
      <h3>问题与回答</h3><p class="quote">{{ audit.query }}</p>
      <p v-if="audit.answer?.answer" class="quote">{{ audit.answer.answer }}</p>
      <p v-else class="muted">本次没有返回答案正文。</p>
      <p class="muted">{{ audit.answer?.validation === 'source_and_quote_checked' ? '回答时引用与原文对应' : audit.run.mode === 'general_chat' ? '通用回答，未检索企业资料' : '未返回已核验答案' }}</p>
      <details v-if="audit.answer?.citations.length"><summary>回答引用（{{ audit.answer.citations.length }}）</summary>
        <article v-for="item in audit.answer.citations" :key="item.evidence_id + item.quote" class="module-stack">
          <blockquote class="quote">{{ item.quote }}</blockquote><p class="identifier">{{ item.source.source_locator }}</p>
        </article>
      </details>
      <details v-if="audit.raw"><summary>原始召回（{{ audit.raw.candidates.length }}）</summary>
        <p class="muted">原始排名和相似度按召回时记录显示；后处理结果单独展示。</p>
        <article v-for="candidate in audit.raw.candidates" :key="candidate.candidate_id" class="evidence-row module-stack">
          <div class="row"><strong>原始候选 {{ candidate.rank }}</strong><span>相似度 {{ candidate.similarity_score.toFixed(4) }}</span></div>
          <p class="identifier">{{ candidate.candidate_id }} · {{ candidate.source.source_locator }}</p>
          <blockquote class="quote">{{ candidate.text }}</blockquote><p class="identifier">SHA-256：{{ candidate.content_hash }}</p>
        </article>
      </details>
      <details v-if="audit.processing.length"><summary>后处理（{{ audit.processing.length }}）</summary>
        <article v-for="run in audit.processing" :key="run.id" class="module-stack">
          <p class="identifier">{{ run.id }} · {{ run.status }}</p><p>{{ run.processors.length ? run.processors.join(' → ') : '直接保留原始候选' }}</p>
          <ol><li v-for="id in run.selected_candidate_ids" :key="id" class="identifier">{{ id }}</li></ol>
        </article>
      </details>
      <details v-if="audit.evaluations.length"><summary>独立评价（{{ audit.evaluations.length }}）</summary>
        <article v-for="value in audit.evaluations" :key="value.id" class="evidence-row module-stack">
          <p>{{ value.evaluator }} · {{ value.decision }} · {{ value.score ?? '未评分' }}</p>
          <p class="identifier">{{ value.candidate_id ?? '事件级评价' }} · {{ value.created_at }}</p><p class="quote">{{ value.reason }}</p>
          <p v-if="value.evaluator === 'user_feedback'" class="muted">用户相关性反馈，尚未复核。</p>
        </article>
      </details>
      <details v-if="audit.answer?.evidence_bundle"><summary>回答时的证据与来源链</summary><EvidencePanel :items="audit.answer.evidence_bundle.items" /></details>
      <details><summary>追加评价或纠错</summary><AnswerFeedback :request-id="audit.run.request_id" :event-id="audit.run.execution_feedback.retrieval_event_id" :answered="audit.run.status === 'answered'" :candidates="(audit.raw?.candidates ?? []).map(item => ({ id: item.candidate_id, label: `原始候选 ${item.rank} · ${item.source.source_locator}` }))" @recorded="emit('refresh')" /></details>
    </template>
    <h3>用户反馈（{{ audit.run.feedback_count }}）</h3>
    <p v-if="!audit.feedback.length" class="muted">本次尚无用户反馈。</p>
    <p v-if="audit.feedback_truncated" class="notice">显示最近 100 条反馈。</p>
    <article v-for="item in audit.feedback" :key="item.id" class="evidence-row module-stack">
      <div class="row"><strong>{{ kinds[item.kind] }}</strong><span class="badge">待复核</span></div>
      <p>{{ values[item.value] ?? item.value }}{{ item.origin === 'automated_test' ? ' · 自动化验证记录' : '' }}</p>
      <p v-if="item.comment" class="quote">{{ item.comment }}</p>
      <p class="identifier">{{ item.actor_user_id }} · {{ item.created_at }} · {{ item.id }}</p>
      <p v-if="item.candidate_id" class="identifier">候选：{{ item.candidate_id }}</p>
    </article>
    <details><summary>授权事件与策略版本（最近 {{ audit.authorization.length }} 条）</summary>
      <article v-for="event in audit.authorization" :key="event.id" class="evidence-row module-stack">
        <p>{{ event.action }} · {{ event.decision }} · {{ event.principal_id }}</p>
        <p class="identifier">{{ event.created_at }} · {{ event.policy_version }}</p>
      </article>
    </details>
    <p class="muted">本次读取已重新检查当前资料访问范围：{{ audit.checked_at }}。来源链显示回答时保存的核验事实。</p>
  </section>
</template>
<script setup lang="ts">
import { AnswerFeedback, EvidencePanel, RunFeedbackPanel } from '../../qa'
import type { RunAudit } from '../types'
defineProps<{ audit: RunAudit }>()
const emit = defineEmits<{ refresh: [] }>()
const kinds: Record<string, string> = { answer_helpfulness: '回答帮助度', candidate_relevance: '候选相关性', factual_correction: '事实纠错' }
const values: Record<string, string> = { helpful: '有帮助', not_helpful: '没有帮助', relevant: '相关', not_relevant: '不相关', correction: '纠错说明' }
</script>
