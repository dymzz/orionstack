import { getJson, postJson, postEventStream, ApiError } from '../../shared/http'
import type { QueryResponse, GeneralChatResponse, ChatMessage, FeedbackResponse, RunFeedback, UserFeedbackRequest, UserFeedbackResponse, Transcript } from './types'
export function queryKnowledge(query: string, documentIds: string[]) {
  return postJson<QueryResponse>('/api/query', { query, document_ids: documentIds, top_k: 20, final_top_k: 5 }, 180_000)
}

export function chatGeneral(query: string, messages: ChatMessage[]) {
  return postJson<GeneralChatResponse>('/api/chat', { query, messages }, 180_000)
}
export function getExecutionFeedback(requestId: string) {
  return getJson<FeedbackResponse>(`/api/workbench/runs/${encodeURIComponent(requestId)}/feedback`)
}
export function failureFeedback(cause: unknown): RunFeedback | null {
  if (!(cause instanceof ApiError)) return null
  try {
    const feedback = JSON.parse(cause.message)?.execution_feedback
    if (typeof feedback?.request_id === 'string' && ['knowledge', 'general_chat'].includes(feedback.mode)
        && feedback.outcome === 'failed' && ['skipped', 'succeeded', 'failed', 'unknown'].includes(feedback.model_call?.status)) return feedback
  } catch { /* A network/authentication failure may have no execution receipt. */ }
  return null
}

export function submitUserFeedback(payload: UserFeedbackRequest) { return postJson<UserFeedbackResponse>('/api/feedback', payload) }

export function createConversation() { return postJson<{ thread_id: string }>('/api/chat/threads', {}) }
export function listConversations() { return getJson<{ items: { thread_id: string; created_at: string }[] }>('/api/chat/threads') }
export function conversationTranscript(id: string) { return getJson<Transcript>(`/api/chat/${encodeURIComponent(id)}/messages`, 180_000) }
export function sendChatMessage(id: string, message: string, clientMessageId: string, onEvent: (event: any) => void) {
  return postEventStream(`/api/chat/${encodeURIComponent(id)}/messages`, { message, client_message_id: clientMessageId }, onEvent)
}
