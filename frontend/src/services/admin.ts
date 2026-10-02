import { getJson, postJson } from './api'
import type {
  TraceRecord,
  HardCaseListResponse,
  ExtractionListResponse,
  ExtractRequest,
  ExtractResponse,
  ReviewRequest,
  ReviewResponse,
} from '../types/admin'

export async function getTrace(traceId: string): Promise<TraceRecord> {
  return await getJson<TraceRecord>(`/api/v1/chat/traces/${traceId}`)
}

export async function listHardCases(limit = 50): Promise<HardCaseListResponse> {
  return await getJson<HardCaseListResponse>(`/api/v1/chat/hard-cases?limit=${limit}`)
}

export async function listExtractionCandidates(status = 'pending'): Promise<ExtractionListResponse> {
  return await getJson<ExtractionListResponse>(`/api/v1/extraction/candidates?status=${status}`)
}

export async function extractCandidates(request: ExtractRequest): Promise<ExtractResponse> {
  return await postJson<ExtractResponse>('/api/v1/extraction/extract', request)
}

export async function reviewCandidate(request: ReviewRequest): Promise<ReviewResponse> {
  return await postJson<ReviewResponse>('/api/v1/extraction/review', {
    candidate_id: request.candidate_id,
    approved: request.action === 'approve',
  })
}
