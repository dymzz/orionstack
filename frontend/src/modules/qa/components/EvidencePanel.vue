<template>
  <section class="module-stack">
    <p class="muted">来源链验证身份、版本、位置和内容对应；相关性、冲突和覆盖分别评价。</p>
    <p v-if="!items.length">本次没有可返回的证据。</p>
    <article v-for="item in items" :key="item.evidence_id" class="evidence-row module-stack">
      <div class="row"><strong>候选 {{ item.raw_rank ?? '—' }}</strong><span class="badge">来源链：{{ labels[item.chain.status] }}</span></div>
      <dl class="facts">
        <dt>来源系统</dt><dd>{{ item.chain.source.source_system ?? '未知' }}</dd>
        <dt>来源 ID</dt><dd class="identifier">{{ item.source.source_id }}</dd>
        <dt>版本</dt><dd class="identifier">{{ item.source.source_version }}</dd>
        <dt>最新版本</dt><dd>{{ item.chain.source.version.is_latest === null ? '未知' : item.chain.source.version.is_latest ? '是（本地已知版本）' : '否（本地已有新版）' }}</dd>
        <dt>来源主体</dt><dd>{{ item.chain.source.actor.published_by ?? item.chain.source.actor.owner ?? '未知' }}</dd>
        <dt>原始产生时间</dt><dd>{{ item.chain.source.time.created_at ?? '未知' }}</dd>
        <dt>本次观察时间</dt><dd>{{ item.chain.source.time.observed_at }}</dd>
        <dt>原始位置</dt><dd class="identifier">{{ item.source.source_locator }}</dd>
        <dt>向量相似度</dt><dd>{{ item.vector_score === null ? '不适用' : item.vector_score.toFixed(4) }}</dd>
      </dl>
      <blockquote v-if="item.chain.content.kind === 'document'" class="quote">{{ item.chain.content.text }}</blockquote>
      <details>
        <summary>逐项核验与追溯标识</summary>
        <table class="checks-table"><thead><tr><th>检查</th><th>状态</th></tr></thead><tbody><tr v-for="(check, name) in item.chain.checks" :key="name"><td>{{ checkNames[name] ?? name }}</td><td>{{ labels[check.status] }}</td></tr></tbody></table>
        <p class="muted">来源主体、原始时间与最新版本状态独立显示；未知项不视为通过。</p>
        <dl class="facts"><dt>证据 ID</dt><dd class="identifier">{{ item.evidence_id }}</dd><dt>来源链 ID</dt><dd class="identifier">{{ item.chain.chain_id }}</dd><dt>Raw 记录</dt><dd class="identifier">{{ item.chain.raw_record_id }}</dd><dt>内容 SHA-256</dt><dd class="identifier">{{ item.chain.content.hash.digest }}</dd></dl>
      </details>
      <p v-for="evaluation in item.evaluations" :key="evaluation.evaluator + evaluation.evaluator_version" class="muted">{{ evaluation.evaluator }}：{{ evaluation.decision }} · {{ evaluation.score ?? '未评分' }}</p>
    </article>
  </section>
</template>
<script setup lang="ts">
import type { EvidenceItem } from '../types'
defineProps<{ items: EvidenceItem[] }>()
const labels = { pass: '已核验', fail: '不一致', unknown: '未知', not_applicable: '不适用' }
const checkNames: Record<string, string> = { source_identity: '来源身份', source_actor: '来源主体', source_time: '原始时间', source_version: '确定版本', latest_version: '本地最新版本', source_locator: '原始位置', content_integrity: '内容完整性', raw_link: 'Raw 关联' }
</script>
