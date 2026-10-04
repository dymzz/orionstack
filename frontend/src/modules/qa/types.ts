export type CheckStatus = 'pass' | 'fail' | 'unknown' | 'not_applicable'
export interface SourceRef {
  source_id: string; source_version: string; source_locator: string
  document_id: string | null; document_version: string | null; chunk_id: string | null
  record_id: string | null; content_hash: string | null
}
export interface ChainProfile {
  tenant_id: string
  schema_version: '1'; chain_id: string; evidence_id: string; raw_record_id: string; raw_event_id: string
  source: {
    source_id: string; source_system: string | null; external_id: string | null; source_type: 'document' | 'structured_record'
    actor: { owner: string | null; published_by: string | null }
    time: { created_at: string | null; updated_at: string | null; observed_at: string }
    version: { value: string; latest: string | null; is_latest: boolean | null; checked_at: string | null; scope: 'local_catalog' }
  }
  locator: { kind: 'document'; document_id: string; document_version: string; chunk_id: string; source_locator: string } |
    { kind: 'structured_record'; table: string; primary_key: { name: string; value: string | number | boolean | null }[]; fields: string[] }
  content: { kind: 'document'; text: string; hash: ContentHash } |
    { kind: 'structured_record'; fields: { name: string; value: string | number | boolean | null }[]; hash: ContentHash }
  verification: { profile: 'source_trace_v1'; required_checks: string[]; checked_at: string }
  checks: Record<string, { status: CheckStatus; reason: string }>
  status: CheckStatus
}
export interface ContentHash { algorithm: 'sha256'; digest: string; scope: 'chunk' | 'authorized_fields'; encoding: 'utf-8' | 'typed_fields_json_v1' }
export interface EvidenceItem {
  tenant_id: string
  evidence_id: string; evidence_kind: 'document_chunk' | 'structured_record'; source: SourceRef
  raw_rank: number | null; vector_score: number | null; chain: ChainProfile
  evaluations: { evaluator: string; evaluator_version: string; decision: string; score: number | null; reason: string }[]
}
export interface QueryResponse {
  tenant_id: string; runtime_versions: Record<string, string | null>
  status: 'answered' | 'insufficient_evidence'; answer: string
  citations: { evidence_id: string; quote: string; source: SourceRef }[]
  validation: 'source_and_quote_checked' | 'no_verified_answer'; model: string | null
  request_id: string; retrieval_event_id: string; processing_run_id: string; processing_status: string
  raw_candidate_count: number; final_candidate_count: number; checked_at: string
  evidence_bundle: { tenant_id: string; schema_version: '1'; retrieval_event_id: string; processing_run_id: string;
    items: EvidenceItem[]; conflict_status: 'not_checked'; coverage_status: 'not_checked' } | null
  execution_feedback: RunFeedback | null
}

export type WorkbenchMode = 'knowledge' | 'general_chat'
export interface ModelCallReceipt {
  provider: 'deepseek'; status: 'skipped' | 'succeeded' | 'failed' | 'unknown'
  attempted: boolean | null; model: string | null; reason: string; error_code: string | null
}
export interface RunFeedback {
  request_id: string; mode: WorkbenchMode; outcome: 'answered' | 'insufficient_evidence' | 'failed'
  reason: string; model_call: ModelCallReceipt; retrieval_event_id: string | null; processing_run_id: string | null
  raw_candidate_count: number | null; final_candidate_count: number | null; audit_status: 'stored' | 'unavailable'
  recorded_at: string; runtime_versions: Record<string, string | null>
}
export interface ChatMessage { role: 'user' | 'assistant'; content: string }
export interface GeneralChatResponse {
  tenant_id: string; request_id: string; mode: 'general_chat'; status: 'answered'; answer: string
  validation: 'unverified_general_response'; model: string; execution_feedback: RunFeedback
}
export interface FeedbackResponse { tenant_id: string; user_id: string; execution_feedback: RunFeedback }

export interface UserFeedbackRequest {
  request_id: string; idempotency_key: string; event_id?: string | null; candidate_id?: string | null
  kind: 'answer_helpfulness' | 'candidate_relevance' | 'factual_correction'
  value: 'helpful' | 'not_helpful' | 'relevant' | 'not_relevant' | 'correction'; comment?: string
  origin?: 'user_submission' | 'automated_test'
}
export interface UserFeedbackEntry {
  tenant_id: string; id: string; request_id: string; actor_user_id: string; event_id: string | null; candidate_id: string | null
  kind: UserFeedbackRequest['kind']; value: string; comment: string | null; origin: 'user_submission' | 'automated_test'
  evaluator: 'user_feedback'; review_state: 'unreviewed'; training_eligible: false; policy_version: string; created_at: string
}
export interface UserFeedbackResponse { feedback: UserFeedbackEntry; replayed: boolean }

export interface RouteDecision { needs_retrieval: boolean; is_feedback: boolean; is_system_status: boolean; needs_workflow: false; retrieval_query: string; feedback_value: string; reason: string }
export interface ChatOutput { thread_id: string; client_message_id: string; kind: 'knowledge' | 'general_chat' | 'system' | 'failure'; message: string; route: RouteDecision | null; routing_call: ModelCallReceipt | null; result: QueryResponse | GeneralChatResponse | null; execution_feedback: RunFeedback | null; feedback: UserFeedbackEntry | null; error_code: string | null; replayed: boolean }
export interface Transcript { thread_id: string; items: { client_message_id: string; message: string | null; response: ChatOutput | null; content_access: 'available' | 'withheld'; created_at: string }[] }
