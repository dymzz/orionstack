<template>
  <div>
    <div class="admin-page-head">
      <div>
        <h2>抽取候选审核</h2>
        <p class="admin-subtitle">查看 LLM 抽取的 FAQ / ActionLink / DynamicQuery 候选，逐条审核发布。</p>
      </div>
      <div class="admin-actions">
        <button
          v-for="s in statusFilters"
          :key="s"
          class="ghost-button"
          :class="{ 'nav-link-active': currentStatus === s }"
          @click="switchStatus(s)"
        >
          {{ s }}
        </button>
        <button class="ghost-button" :disabled="loading" @click="fetchCandidates">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <p v-if="message" class="admin-message">{{ message }}</p>
    <p v-if="!loading && candidates.length === 0" class="admin-empty">暂无 {{ currentStatus }} 候选。</p>

    <div v-else class="admin-card-list">
      <section v-for="item in candidates" :key="item.candidate_id" class="card admin-case-card">
        <div class="admin-case-head">
          <div class="admin-case-badges">
            <span class="badge badge-issue">{{ item.candidate_type }}</span>
            <span class="badge" :class="reviewStatusClass(item.review_status)">{{ item.review_status }}</span>
          </div>
          <code class="admin-trace-id">{{ item.candidate_id }}</code>
        </div>
        <dl class="admin-case-meta">
          <div><dt>source_record</dt><dd><code>{{ item.source_record_id }}</code></dd></div>
          <div><dt>model</dt><dd>{{ item.extractor_model }}</dd></div>
          <div><dt>prompt_version</dt><dd>{{ item.prompt_version }}</dd></div>
          <div><dt>created_at</dt><dd>{{ item.created_at }}</dd></div>
          <div v-if="item.reviewed_by"><dt>reviewed_by</dt><dd>{{ item.reviewed_by }}</dd></div>
          <div v-if="item.reviewed_at"><dt>reviewed_at</dt><dd>{{ item.reviewed_at }}</dd></div>
        </dl>
        <details class="record-details" open>
          <summary>payload</summary>
          <pre class="admin-payload">{{ formatPayload(item.payload_json) }}</pre>
        </details>
        <details v-if="item.source_span" class="record-details">
          <summary>source_span</summary>
          <p class="admin-span-text">{{ item.source_span }}</p>
        </details>
        <div v-if="item.review_status === 'pending'" class="admin-review-actions">
          <button class="primary-button" :disabled="reviewingId === item.candidate_id" @click="review(item.candidate_id, 'approve')">
            {{ reviewingId === item.candidate_id ? '处理中...' : '通过并发布' }}
          </button>
          <button class="ghost-button" :disabled="reviewingId === item.candidate_id" @click="review(item.candidate_id, 'reject')">
            拒绝
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listExtractionCandidates, reviewCandidate } from '../../services/admin'
import type { ExtractionCandidate } from '../../types/admin'

const statusFilters = ['pending', 'approved', 'rejected'] as const
const currentStatus = ref<string>('pending')
const loading = ref(false)
const message = ref('')
const candidates = ref<ExtractionCandidate[]>([])
const reviewingId = ref('')

async function fetchCandidates() {
  loading.value = true
  message.value = ''
  try {
    const result = await listExtractionCandidates(currentStatus.value)
    candidates.value = result.items
  } catch (error) {
    message.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function switchStatus(status: string) {
  currentStatus.value = status
  void fetchCandidates()
}

async function review(candidateId: string, action: 'approve' | 'reject') {
  reviewingId.value = candidateId
  message.value = ''
  try {
    await reviewCandidate({ candidate_id: candidateId, action })
    message.value = action === 'approve' ? '已发布' : '已拒绝'
    await fetchCandidates()
  } catch (error) {
    message.value = error instanceof Error ? error.message : '审核失败'
  } finally {
    reviewingId.value = ''
  }
}

function reviewStatusClass(status: string) {
  if (status === 'approved') return 'badge-status-ok'
  if (status === 'rejected') return 'badge-status-refused'
  return 'badge-status-fallback'
}

function formatPayload(raw: string) {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

onMounted(() => { void fetchCandidates() })
</script>
