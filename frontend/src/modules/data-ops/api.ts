import { getJson, postJson } from '../../shared/http'
import type { DataOpsConfig, UploadGrant, AssetVersion, Backup, BackupFile } from './types'
export const getConfig = () => getJson<DataOpsConfig>('/api/dataops/config')
export function requestUpload(file: File) {
  return postJson<UploadGrant>('/api/assets/uploads', {
    filename: file.name, relative_path: file.webkitRelativePath || '', size_bytes: file.size,
    media_type_hint: file.type || 'application/octet-stream', kind: 'file',
    attachment: { resource_type: 'collection', resource_id: 'uploads', relation: 'other' },
  })
}
export const finalizeUpload = (id: string) => postJson<AssetVersion>(`/api/assets/versions/${encodeURIComponent(id)}/finalize`, {}, 180_000)
export const readVersion = (id: string) => getJson<AssetVersion>(`/api/assets/versions/${encodeURIComponent(id)}`)
export const getBackups = () => getJson<{ status: string; items: Backup[] }>('/api/backups')
export const getBackupFiles = (id: string) => getJson<{ items: BackupFile[] }>(`/api/backups/${encodeURIComponent(id)}/files`)
export const backupDownload = (id: string, name: string) => `/api/backups/${encodeURIComponent(id)}/download?filename=${encodeURIComponent(name)}`
