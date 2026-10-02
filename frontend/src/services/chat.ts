import { getJson, postJson, CHAT_TIMEOUT_MS } from './api'
import type {
  ChatAskRequest,
  ChatAskResponse,
  ChatFeedbackRequest,
  ChatFeedbackResponse,
  ChatRecordListResponse,
  FeedbackRecordListResponse,
} from '../types/chat'

export async function askQuestion(
  rawQuery: string,
  debug = import.meta.env.DEV,
  documentIds: string[] = [],
): Promise<ChatAskResponse> {
  const payload: ChatAskRequest = { raw_query: rawQuery, debug, document_ids: documentIds }
  return await postJson<ChatAskResponse>('/api/v1/chat/ask', payload, CHAT_TIMEOUT_MS)
}

export async function submitFeedback(payload: ChatFeedbackRequest): Promise<ChatFeedbackResponse> {
  return await postJson<ChatFeedbackResponse>('/api/v1/chat/feedback', payload)
}

export async function listChatRecords(limit = 20): Promise<ChatRecordListResponse> {
  return await getJson<ChatRecordListResponse>(`/api/v1/chat/records?limit=${limit}`)
}

export async function listFeedbackRecords(limit = 20): Promise<FeedbackRecordListResponse> {
  return await getJson<FeedbackRecordListResponse>(`/api/v1/chat/feedback?limit=${limit}`)
}
