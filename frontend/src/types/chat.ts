export interface ChatAskRequest {
  raw_query: string
  debug?: boolean
}

export type FeedbackLabel = 'up' | 'down'

export interface CitationItem {
  citation_id: string
  source_label: string
  source_locator: string
  snippet: string
}

export interface DebugInfo {
  normalized_query: string
  route_result: string
  router_used: string
  retrieved_chunks: string[]
  route_confidence?: number
  retrieval_score?: number
  fallback_reason?: string
}

export interface ChatAskResponse {
  response_status: 'ok' | 'refused' | 'fallback' | 'system_error'
  trace_id: string
  answer: string
  citations: CitationItem[]
  debug_info?: DebugInfo
}

export interface ChatFeedbackRequest {
  trace_id: string
  raw_query: string
  answer_text: string
  feedback_label: FeedbackLabel
  response_status: ChatAskResponse['response_status']
  retrieved_chunk_ids: string[]
  normalized_query?: string
  router_used?: string
  route_result?: string
  fallback_reason?: string
}

export interface ChatFeedbackResponse {
  status: 'recorded'
}
