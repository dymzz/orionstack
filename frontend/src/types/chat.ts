export interface ChatAskRequest {
  raw_query: string
  debug?: boolean
  document_ids?: string[]
}

export type FeedbackLabel = 'up' | 'down'
export type ResponseStatus = 'ok' | 'refused' | 'fallback' | 'system_error'

export interface CitationItem {
  citation_id: string
  source_label: string
  source_locator: string
  snippet: string
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

export interface DebugInfo {
  normalized_query: string
  route_result: string
  router_used: string
  retrieved_chunks: string[]
  route_confidence?: number
  retrieval_score?: number
  fusion_score?: number
  fallback_reason?: string | null
  domain_hint?: string | null
  lexical_terms?: string[] | null
  semantic_expansions?: string[] | null
  planner_confidence?: number | null
}

export interface ChatAskResponse {
  response_status: ResponseStatus
  trace_id: string
  answer: string
  citations: CitationItem[]
  clarification?: ClarificationInfo | null
  debug_info?: DebugInfo
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
