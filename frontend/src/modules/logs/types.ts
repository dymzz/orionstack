import type { EvidenceItem, RunFeedback, UserFeedbackEntry, SourceRef } from '../qa'
export interface RunSummary {
  request_id: string; actor_user_id: string; mode: 'knowledge' | 'general_chat'
  status: 'answered' | 'insufficient_evidence' | 'failed'; created_at: string; execution_feedback: RunFeedback; feedback_count: number
}
export interface RunList { tenant_id: string; scope: 'mine'; items: RunSummary[]; next_cursor: string | null }
export interface RawCandidate {
  candidate_id: string; document_id: string; document_version: string; chunk_id: string
  rank: number; similarity_score: number; content_hash: string; text: string; source: SourceRef
}
export interface Evaluation {
  id: string; candidate_id: string | null; evaluator: string; evaluator_version: string
  decision: string; score: number | null; reason: string; details_json: string; created_at: string
}
export interface RunAudit {
  tenant_id: string; run: RunSummary; content_access: 'available' | 'withheld'; query: string | null
  messages: { role: 'user' | 'assistant'; content: string }[]
  raw: { event: { id: string; query: string; embedding_configuration: Record<string, unknown>; candidate_count: number }; candidates: RawCandidate[] } | null
  processing: { id: string; status: string; processors: string[]; selected_candidate_ids: string[]; evaluations: Evaluation[] }[]
  evaluations: Evaluation[]
  answer: { status: string; answer: string | null; validation: string | null; model: string | null
    citations: { evidence_id: string; quote: string; source: SourceRef }[]; evidence_bundle: { items: EvidenceItem[] } | null } | null
  feedback: UserFeedbackEntry[]; feedback_truncated: boolean; checked_at: string
  authorization: { id: string; principal_id: string; action: string; resource_id: string; decision: string; policy_version: string; created_at: string }[]
}
