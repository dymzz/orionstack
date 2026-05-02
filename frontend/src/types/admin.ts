export interface TraceRecord {
  trace_id: string
  raw_query: string
  normalized_query: string
  intent?: string | null
  router_used?: string | null
  retrieval_score?: number | null
  fusion_score?: number | null
  domain_hint?: string | null
  retrieval_mode?: string | null
  fallback_reason?: string | null
  final_status: string
  retrieved_chunks: string[]
  citations: Array<{
    citation_id: string
    source_label: string
    source_locator: string
    snippet: string
  }>
  source_record_id?: string | null
  import_batch_id?: string | null
  unit_version?: number | null
  dynamic_query_key?: string | null
  created_at?: string
}

export interface HardCaseItem {
  trace_id: string
  raw_query: string
  normalized_query: string
  router_used?: string | null
  domain_hint?: string | null
  fallback_reason?: string | null
  user_feedback?: string | null
  issue_category?: string | null
  source_record_id?: string | null
  import_batch_id?: string | null
  unit_version?: number | null
  dynamic_query_key?: string | null
  top_candidates?: Array<Record<string, unknown>>
  evidence_spans?: Array<{ text: string }>
  created_at?: string
}

export interface HardCaseListResponse {
  items: HardCaseItem[]
}

export interface ExtractionCandidate {
  candidate_id: string
  tenant_id: string
  source_record_id: string
  candidate_type: string
  payload_json: string
  extractor_model: string
  prompt_version: string
  source_span: string
  source_span_hash: string
  review_status: string
  created_at: string
  reviewed_by?: string | null
  reviewed_at?: string | null
}

export interface ExtractionListResponse {
  items: ExtractionCandidate[]
}

export interface ExtractRequest {
  source_record_id: string
  candidate_types?: string[]
}

export interface ExtractResponse {
  source_record_id: string
  extracted_count: number
  candidates: ExtractionCandidate[]
}

export interface ReviewRequest {
  candidate_id: string
  action: 'approve' | 'reject'
}

export interface ReviewResponse {
  candidate_id: string
  review_status: string
  reviewed_by?: string | null
  reviewed_at?: string | null
  published_type?: string | null
}
