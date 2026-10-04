export interface AccessContext {
  tenant_id: string
  user_id: string
  roles: string[]
  allowed_scopes: string[]
  permissions: {
    query: boolean
    documents_read: boolean
    documents_maintain: boolean
    accounts_manage: boolean
    backups_manage: boolean
    audit_read: boolean
  }
}
