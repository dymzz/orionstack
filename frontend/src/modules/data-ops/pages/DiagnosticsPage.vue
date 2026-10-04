<template>
  <section class="card module-stack">
    <div class="row"><h2>系统状态</h2><RouterLink to="/admin/account">账号权限</RouterLink><a v-if="data" href="/api/support/diagnostics?export=true" download>导出诊断包</a></div>
    <p>诊断包包含版本、依赖状态与计数，不包含密钥、用户输入或原文。</p>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <template v-if="data">
      <table class="checks-table"><thead><tr><th>服务</th><th>状态</th></tr></thead><tbody><tr v-for="(status, name) in data.service_health" :key="name"><td>{{ name }}</td><td>{{ statusName(status) }}</td></tr></tbody></table>
      <p>最后入库：{{ data.last_ingestion || '尚未记录' }} · 待核验附件：{{ data.pending_asset_versions ?? '未知' }} · 已拒绝：{{ data.rejected_asset_versions ?? '未知' }}</p>
      <p class="muted">最近附件核验：{{ data.last_asset_ready || '尚无记录' }} · 队列积压：{{ data.queue_backlog ?? '未知' }} · 失败任务：{{ data.failed_jobs ?? '未知' }}</p>
      <details><summary>版本与配置指纹</summary><pre class="quote">{{ JSON.stringify(data.versions, null, 2) }}</pre><p class="identifier">{{ data.configuration_fingerprint }}</p></details>
      <p class="notice">保留期限尚未配置的类别标记为“待确定”；当前不自动删除数据。联合恢复测试尚未执行。</p>
    </template>
  </section>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { getJson, errorMessage } from '../../../shared/http'
const data = ref<any>(null), error = ref('')
const statusName = (s: string) => ({ ok: '正常', unavailable: '不可用', unknown: '未知', missing: '缺失', not_configured: '待配置', configured_unchecked: '已配置，未检查', demo_identity: '开发演示身份' }[s] || s)
onMounted(async () => { try { data.value = await getJson('/api/support/diagnostics') } catch (e) { error.value = errorMessage(e) } })
</script>
