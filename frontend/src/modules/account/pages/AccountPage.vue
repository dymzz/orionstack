<template>
  <section class="card module-stack">
    <h2>账号与权限</h2>
    <div class="row"><RouterLink to="/support/diagnostics">系统状态</RouterLink><RouterLink to="/admin/debug">开发调试</RouterLink></div>
    <p>当前账号：{{ currentUsername }} · 角色：{{ currentRole }}</p>
    <dl class="facts"><dt>内部主体 ID</dt><dd>{{ principalId }}</dd><dt>身份来源</dt><dd>{{ authentication === 'oidc' ? '外部 OIDC IdP' : '本地演示' }}</dd></dl>
    <p v-if="accessError" role="alert" class="error-message">{{ accessError }}</p>
    <template v-if="accessContext">
      <dl class="facts"><dt>租户</dt><dd>{{ accessContext.tenant_id }}</dd><dt>访问范围</dt><dd>{{ accessContext.allowed_scopes.join('、') }}</dd></dl>
      <p>问答：{{ permissions?.query ? '可用' : '不可用' }} · 附件与备份权限由操作入口的 Cedar 策略判断。</p>
    </template>
    <p class="muted">账户与角色管理服务尚未接入，当前页面提供实际会话与服务端授权信息。</p>
  </section>
</template>
<script setup lang="ts">
import { useAuthState } from '../session'
import { RouterLink } from 'vue-router'
const { currentUsername, currentRole, principalId, authentication, accessContext, accessError, permissions } = useAuthState()
</script>
