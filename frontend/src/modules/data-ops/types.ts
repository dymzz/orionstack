export interface DataOpsConfig {
  dependencies: { object_storage: boolean; tika: boolean; clamav: boolean; pgbackrest: boolean; tus: boolean }
  permissions: { assets_upload: boolean; backups_read: boolean; backups_download: boolean; diagnostics_read: boolean }
  policy_bundle_version: string; max_upload_bytes: number
}
export interface AssetVersion {
  tenant_id: string; asset_id: string; asset_version_id: string; version: number
  original_filename: string; relative_path: string; size_bytes: number
  sha256: string | null; media_type: string | null
  status: 'uploading' | 'quarantined' | 'scanning' | 'ready' | 'rejected'; rejection_code: string | null
}
export interface UploadGrant { version: AssetVersion; url: string; method: 'PUT'; headers: Record<string, string> }
export interface Backup { backup_id: string; type: string; created_at: number | null; size_bytes: number | null; status: string; object_storage_state: string; restore_test: string }
export interface BackupFile { filename: string; size_bytes: number | null }
