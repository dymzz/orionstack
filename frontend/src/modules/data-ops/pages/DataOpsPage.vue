<template>
  <section class="module-stack">
    <div class="row"><h2>数据与备份</h2><RouterLink v-if="config?.permissions.diagnostics_read" to="/support/diagnostics">系统状态</RouterLink></div>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <section class="card module-stack">
      <h3>上传附件</h3><p class="muted">选择文件或文件夹。原文件独立保留，上传后进行隔离检查。</p>
      <p v-if="config && !config.permissions.assets_upload" class="notice">当前身份没有上传权限。</p>
      <p v-else-if="config && !uploadConfigured" class="notice">上传服务待配置：{{ missingUploadServices }}。可以选择文件查看待上传清单。</p>
      <div class="row">
        <label>选择文件<input type="file" multiple :disabled="busy || !config?.permissions.assets_upload" @change="selectFiles" /></label>
        <label>选择文件夹<input type="file" multiple webkitdirectory directory :disabled="busy || !config?.permissions.assets_upload" @change="selectFiles" /></label>
      </div>
      <ul class="upload-list"><li v-for="item in uploads" :key="item.id" class="evidence-row">
        <div class="row"><strong>{{ item.path }}</strong><span class="badge">{{ labels[item.status] || item.status }}</span></div>
        <p class="muted">{{ formatBytes(item.size) }}<template v-if="item.version"> · 版本 {{ item.version.version }}</template></p>
        <p v-if="item.message" class="muted">{{ item.message }}</p>
        <p v-if="item.version?.sha256" class="identifier">SHA-256 {{ item.version.sha256 }}</p>
        <p v-if="item.version?.media_type" class="muted">实际媒体类型：{{ item.version.media_type }}</p>
        <button v-if="item.status === 'quarantined' && !busy && item.version" class="secondary-button" @click="retryFinalize(item)">重试隔离检查</button>
        <a v-if="item.status === 'ready' && item.version" :href="'/api/assets/versions/' + encodeURIComponent(item.version.asset_version_id) + '/download'" download>下载原附件</a>
      </li></ul>
      <div class="row"><button class="primary-button" :disabled="busy || !uploads.length || !uploadConfigured || !config?.permissions.assets_upload" @click="startUpload">{{ busy ? '上传与检查中…' : '开始上传' }}</button><button class="secondary-button" :disabled="busy || !uploads.length" @click="clearUploads">清空清单</button></div>
      <p class="muted">单文件上限 128 MiB。文件名和浏览器媒体类型仅作提示；扫描失败会留在隔离区。大文件断点续传将在 tus 服务配置后接入。</p>
      <p class="muted">上传不会自动将图片、发票或图纸写入知识检索；OCR、缩略图和检索文本属于独立派生结果。</p>
    </section>
    <section class="card module-stack">
      <div class="row"><h3>备份</h3><button v-if="config?.dependencies.pgbackrest && config.permissions.backups_read" class="secondary-button" :disabled="backupLoading" @click="loadBackups">刷新状态</button></div>
      <p v-if="config && !config.permissions.backups_read" class="notice">当前身份没有查看备份权限。</p>
      <p v-else-if="config && !config.dependencies.pgbackrest" class="notice">pgBackRest 待配置，暂无可验证的备份记录。</p>
      <p v-if="backupError" class="error-message" role="alert">{{ backupError }}</p>
      <p v-if="backupStatus">仓库状态：{{ backupStatus }}</p>
      <p class="muted">恢复范围包含 PostgreSQL 和对象存储。数据库备份记录与恢复测试分别显示。</p>
      <p v-if="backupStatus && !backups.length" class="notice">仓库暂未返回备份集合。</p>
      <article v-for="backup in backups" :key="backup.backup_id" class="evidence-row module-stack">
        <div class="row"><strong class="identifier">{{ backup.backup_id }}</strong><span class="badge">{{ backup.status === 'database_backup_recorded' ? '数据库备份已记录' : '备份失败' }}</span></div>
        <p class="muted">{{ backup.type }} · {{ backup.created_at ? new Date(backup.created_at * 1000).toLocaleString() : '时间未知' }} · {{ formatBytes(backup.size_bytes) }}</p>
        <p class="notice">对象存储备份状态：未记录 · 恢复测试：未执行 · 联合恢复：未验证</p>
        <button class="secondary-button" @click="loadFiles(backup.backup_id)">查看备份文件名</button>
        <ul v-if="backupFiles[backup.backup_id]" class="upload-list"><li v-for="file in backupFiles[backup.backup_id]" :key="file.filename" class="row">
          <span class="identifier">{{ file.filename }}</span><span class="muted">{{ formatBytes(file.size_bytes) }}</span><a v-if="config?.permissions.backups_download" :href="backupDownload(backup.backup_id, file.filename)" download>下载</a>
        </li></ul>
      </article>
      <p class="muted">一个备份集合包含多个文件；单个下载文件不能代表完整可恢复的备份。备份执行与恢复由 pgBackRest 和部署运维负责。</p>
    </section>
  </section>
</template>
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
import { RouterLink } from 'vue-router'
import Uppy from '@uppy/core'
import AwsS3 from '@uppy/aws-s3'
import { errorMessage } from '../../../shared/http'
import { getConfig, requestUpload, finalizeUpload, getBackups, getBackupFiles, backupDownload } from '../api'
import type { DataOpsConfig, AssetVersion, UploadGrant, Backup, BackupFile } from '../types'
interface UploadItem { id: string; path: string; size: number; status: string; message: string; version?: AssetVersion }
const config = ref<DataOpsConfig | null>(null), error = ref(''), busy = ref(false)
const uploads = ref<UploadItem[]>([]), backups = ref<Backup[]>([]), backupStatus = ref(''), backupError = ref(''), backupLoading = ref(false)
const backupFiles = ref<Record<string, BackupFile[]>>({})
const grants = new Map<string, UploadGrant>()
const labels: Record<string, string> = { selected: '待上传', uploading: '上传中', quarantined: '已隔离，待核验', scanning: '正在核验', ready: '已核验', rejected: '已拒绝', failed: '上传失败' }
const uploadConfigured = computed(() => !!config.value?.dependencies.object_storage && !!config.value.dependencies.tika && !!config.value.dependencies.clamav)
const missingUploadServices = computed(() => [
  !config.value?.dependencies.object_storage ? '对象存储' : '',
  !config.value?.dependencies.tika ? 'Apache Tika' : '', !config.value?.dependencies.clamav ? 'ClamAV' : '',
].filter(Boolean).join('、'))
const formatBytes = (size: number | null) => size == null ? '大小未知' : size < 1024 * 1024 ? (size / 1024).toFixed(1) + ' KiB' : (size / 1024 / 1024).toFixed(1) + ' MiB'
const uppy = new Uppy({ autoProceed: false, restrictions: { maxFileSize: 128 * 1024 * 1024, maxNumberOfFiles: 1000 } })
uppy.use(AwsS3, {
  shouldUseMultipart: false,
  async getUploadParameters(file) {
    const grant = grants.get(file.id) || await requestUpload(file.data as File)
    grants.set(file.id, grant)
    const item = uploads.value.find(i => i.id === file.id)
    if (item) { item.version = grant.version; item.status = 'uploading' }
    return { method: 'PUT', url: grant.url, headers: grant.headers }
  },
})
uppy.on('upload-error', (file) => {
  const item = uploads.value.find(i => i.id === file?.id)
  if (item) { item.status = 'failed'; item.message = '上传未完成；请确认对象存储与网络配置。' }
})
function selectFiles(event: Event) {
  const input = event.target as HTMLInputElement
  for (const file of Array.from(input.files || [])) {
    try {
      const id = uppy.addFile({ name: file.name, type: file.type, data: file, meta: { relativePath: file.webkitRelativePath || file.name } })
      uploads.value.push({ id, path: file.webkitRelativePath || file.name, size: file.size, status: 'selected', message: '' })
    } catch { error.value = '文件重复、为空或超出上传上限，请检查后重新选择。' }
  }
  input.value = ''
}
async function checkItem(item: UploadItem) {
  if (!item.version) return
  item.status = 'quarantined'; item.message = ''
  try {
    item.version = await finalizeUpload(item.version.asset_version_id); item.status = item.version.status
    item.message = item.status === 'rejected' ? '文件核验未通过：' + item.version.rejection_code : ''
  } catch (e) { item.message = errorMessage(e) + ' 文件仍在隔离区。' }
}
async function retryFinalize(item: UploadItem) { busy.value = true; try { await checkItem(item) } finally { busy.value = false } }
async function startUpload() {
  busy.value = true; error.value = ''
  try {
    const result = await uppy.upload()
    for (const file of result?.successful || []) {
      const item = uploads.value.find(i => i.id === file.id)
      if (item && item.status !== 'ready') await checkItem(item)
    }
  } catch (e) { error.value = errorMessage(e) } finally { busy.value = false }
}
function clearUploads() { uppy.cancelAll(); grants.clear(); uploads.value = []; error.value = '' }
async function loadBackups() {
  backupLoading.value = true; backupError.value = ''
  try { const result = await getBackups(); backups.value = result.items; backupStatus.value = result.status }
  catch (e) { backupError.value = errorMessage(e); backups.value = []; backupStatus.value = '' }
  finally { backupLoading.value = false }
}
async function loadFiles(id: string) { try { backupFiles.value[id] = (await getBackupFiles(id)).items } catch (e) { backupError.value = errorMessage(e) } }
onMounted(async () => {
  try { config.value = await getConfig(); if (config.value.permissions.backups_read && config.value.dependencies.pgbackrest) await loadBackups() }
  catch (e) { error.value = errorMessage(e) }
})
onBeforeUnmount(() => uppy.destroy())
</script>
