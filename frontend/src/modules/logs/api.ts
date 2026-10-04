import { getJson } from '../../shared/http'
import type { RunList, RunAudit } from './types'
export function listMyRuns(filters: { cursor?: string; mode?: string; status?: string } = {}) {
  const query = new URLSearchParams({ limit: '20' })
  for (const [key, value] of Object.entries(filters)) if (value) query.set(key, value)
  return getJson<RunList>(`/api/query-runs?${query}`)
}
export function getRunAudit(requestId: string) { return getJson<RunAudit>(`/api/query-runs/${encodeURIComponent(requestId)}`) }
