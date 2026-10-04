<template>
  <section class="card module-stack">
    <div class="row"><h2>日志与审计</h2><button class="secondary-button" :disabled="loading" @click="load()">刷新运行记录</button></div>
    <p>查看自己的真实运行记录。原始召回、后处理、证据、回答和用户反馈分别保存。</p>
    <div class="feedback-buttons">
      <label>问答模式 <select v-model="mode"><option value="">全部模式</option><option value="knowledge">资料问答</option><option value="general_chat">普通聊天</option></select></label>
      <label>运行状态 <select v-model="status"><option value="">全部状态</option><option value="answered">已回答</option><option value="insufficient_evidence">证据不足</option><option value="failed">失败</option></select></label>
    </div>
    <p v-if="error" role="alert" class="error-message">{{ error }}</p>
    <p v-if="loading" role="status" class="muted">正在读取运行记录…</p>
    <p v-if="!loading && !items.length && !error" class="notice">当前身份在此范围尚无运行记录。</p>
    <div v-if="items.length" class="audit-table-wrap"><table class="checks-table"><thead><tr><th>时间 / 请求</th><th>模式</th><th>结果</th><th>用户反馈</th><th>审计</th></tr></thead><tbody>
      <tr v-for="item in items" :key="item.request_id"><td><div>{{ item.created_at }}</div><div class="identifier">{{ item.request_id }}</div></td>
        <td>{{ item.mode === 'knowledge' ? '资料问答' : '普通聊天' }}</td><td>{{ statuses[item.status] }}</td><td>{{ item.feedback_count }}</td>
        <td><button class="secondary-button" :aria-label="`查看运行 ${item.request_id}`" @click="open(item.request_id)">查看详情</button></td></tr>
    </tbody></table></div>
    <button v-if="nextCursor" class="secondary-button" :disabled="loading" @click="load(true)">加载更多运行记录</button>
    <p v-if="reading" role="status" class="muted">正在核对本次运行与当前访问范围…</p>
    <p v-if="detailError" role="alert" class="error-message">{{ detailError }}</p>
    <RunAuditPanel v-if="selected" :key="selected.run.request_id" :audit="selected" @refresh="refreshSelected" />
    <RouterLink to="/">返回工作台</RouterLink>
  </section>
</template>
<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { errorMessage } from '../../../shared/http'
import { listMyRuns, getRunAudit } from '../api'
import type { RunSummary, RunAudit } from '../types'
import RunAuditPanel from '../components/RunAuditPanel.vue'
const route = useRoute(), router = useRouter()
const mode = ref(''), status = ref(''), loading = ref(false), reading = ref(false), error = ref(''), detailError = ref('')
const items = ref<RunSummary[]>([]), nextCursor = ref<string | null>(null), selected = ref<RunAudit | null>(null)
const statuses = { answered: '已回答', insufficient_evidence: '证据不足', failed: '失败' }
let listGeneration = 0, detailGeneration = 0
async function load(more = false) {
  const generation = ++listGeneration; loading.value = true; error.value = ''
  if (!more) { items.value = []; nextCursor.value = null }
  try {
    const page = await listMyRuns({ mode: mode.value, status: status.value, cursor: more ? nextCursor.value ?? undefined : undefined })
    if (generation === listGeneration) { items.value = more ? [...items.value, ...page.items] : page.items; nextCursor.value = page.next_cursor }
  } catch (cause) { if (generation === listGeneration) error.value = errorMessage(cause) }
  finally { if (generation === listGeneration) loading.value = false }
}
async function read(requestId: string) {
  const generation = ++detailGeneration; reading.value = true; detailError.value = ''; selected.value = null
  try { const value = await getRunAudit(requestId); if (generation === detailGeneration) selected.value = value }
  catch (cause) { if (generation === detailGeneration) detailError.value = errorMessage(cause) }
  finally { if (generation === detailGeneration) reading.value = false }
}
async function open(requestId: string) {
  if (route.query.request_id === requestId) await read(requestId)
  else await router.replace({ path: '/logs/retrieval', query: { request_id: requestId } })
}
async function refreshSelected() {
  const id = selected.value?.run.request_id
  if (id) { await read(id); await load() }
}
watch([mode, status], () => load())
watch(() => route.query.request_id, value => { if (typeof value === 'string' && value) void read(value); else { detailGeneration++; selected.value = null } }, { immediate: true })
onMounted(() => load())
onBeforeUnmount(() => { listGeneration++; detailGeneration++ })
</script>
