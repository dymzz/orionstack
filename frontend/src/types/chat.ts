export interface ChatTurn {
  id: string
  query: string
  response: ChatAskResponse | null
  error: string
  timestamp: number
}

export interface ChatAskResponse {
  response_status: 'ok' | 'refused' | 'fallback' | 'system_error'
  trace_id: string
  answer: string
  citations: CitationItem[]
  action_links?: ActionLinkItem[]
  dynamic_query_result?: DynamicQueryResultItem | null
  clarification?: ClarificationInfo | null
  debug_info?: DebugInfo
}

export interface CitationItem {
  citation_id: string
  source_label: string
  source_locator: string
  snippet: string
}

export interface ActionLinkItem {
  action_link_id: string
  label: string
  url: string
  system_type: string
  resource_type: string
}

export interface DynamicQueryResultItem {
  query_key: string
  resource_type: string
  description: string
  data: Record<string, unknown>[]
}

export interface ClarificationOption {
  option_id: string
  label: string
}

export interface ClarificationInfo {
  clarification_required: boolean
  question: string
  options: ClarificationOption[]
  conflict_reason?: string | null
}

export interface RetrievalCandidateSummary {
  unit_id: string
  score: number
  source_kind: string
  lexical_dominance_applied?: boolean | null
  vector_dominance_applied?: boolean | null
}

export interface DebugInfo {
  normalized_query: string
  route_result: string
  router_used: string
  retrieved_chunks: string[]
  route_confidence?: number | null
  retrieval_score?: number | null
  fusion_score?: number | null
  fallback_reason?: string | null
  domain_hint?: string | null
  lexical_terms?: string[] | null
  semantic_expansions?: string[] | null
  planner_confidence?: number | null
  retrieval_mode?: 'lexical_only' | 'hybrid' | 'hybrid_rerank' | 'clarification' | null
  lexical_topk?: RetrievalCandidateSummary[] | null
  vector_topk?: RetrievalCandidateSummary[] | null
  rrf_topk?: RetrievalCandidateSummary[] | null
  rerank_accept?: boolean | null
  rerank_score?: number | null
  evidence_confidence?: number | null
  evidence_span_count?: number | null
  reject_reason?: string | null
  source_record_id?: string | null
  import_batch_id?: string | null
  unit_version?: number | null
  source_updated_at?: string | null
  source_record_status?: string | null
  dynamic_query_key?: string | null
  freshness_status?: string | null
}

export interface ChatAskRequest {
  raw_query: string
  debug?: boolean
  document_ids?: string[]
}

export type FeedbackLabel = 'up' | 'down'
export type ResponseStatus = 'ok' | 'refused' | 'fallback' | 'system_error'

export interface ChatFeedbackRequest {
  trace_id: string
  raw_query: string
  answer_text: string
  feedback_label: FeedbackLabel
  response_status: ResponseStatus
  retrieved_chunk_ids: string[]
  normalized_query?: string
  router_used?: string
  route_result?: string
  fallback_reason?: string
}

export interface ChatFeedbackResponse {
  status: 'recorded'
}

export interface ChatRecordItem {
  trace_id: string
  raw_query: string
  response_status: ResponseStatus | string
  retrieved_chunk_ids: string[]
  created_at: string
  feedback_label?: FeedbackLabel | string | null
}

export interface ChatRecordListResponse {
  items: ChatRecordItem[]
}

export interface FeedbackRecordItem {
  trace_id: string
  raw_query: string
  feedback_label: FeedbackLabel | string
  response_status: ResponseStatus | string
  created_at: string
}

export interface FeedbackRecordListResponse {
  items: FeedbackRecordItem[]
}