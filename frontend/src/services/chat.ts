import { postJson } from './api'
import type { ChatAskRequest, ChatAskResponse, ChatFeedbackRequest, ChatFeedbackResponse } from '../types/chat'

export async function askQuestion(
  rawQuery: string,
  debug = import.meta.env.DEV,
  documentIds: string[] = [],
): Promise<ChatAskResponse> {
  const payload: ChatAskRequest = { raw_query: rawQuery, debug, document_ids: documentIds }
  return await postJson<ChatAskResponse>('/api/chat/ask', payload)
}

export async function submitFeedback(payload: ChatFeedbackRequest): Promise<ChatFeedbackResponse> {
  return await postJson<ChatFeedbackResponse>('/api/chat/feedback', payload)
}
