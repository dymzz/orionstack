import { onMounted, ref } from 'vue'
import { errorMessage } from '../../shared/http'
import { createConversation, listConversations, conversationTranscript, sendChatMessage } from './api'
import type { ChatOutput, QueryResponse, GeneralChatResponse, RunFeedback } from './types'
export interface ChatTurn {
  id: string; question: string; output: ChatOutput | null; response: QueryResponse | null
  general: GeneralChatResponse | null; feedback: RunFeedback | null; error: string; pending: boolean
  draft: string; status: string; steps: string[]; withheld: boolean
}
function makeTurn(id: string, question: string): ChatTurn {
  return { id, question, output: null, response: null, general: null, feedback: null, error: '', pending: false, draft: '', status: '', steps: [], withheld: false }
}
function apply(turn: ChatTurn, output: ChatOutput) {
  turn.output = output; turn.feedback = output.execution_feedback; turn.draft = ''
  if (output.kind === 'knowledge') turn.response = output.result as QueryResponse
  if (output.kind === 'general_chat') turn.general = output.result as GeneralChatResponse
  if (output.kind === 'failure') turn.error = output.message
}
export function useQuery() {
  const question = ref(''), loading = ref(true), turns = ref<ChatTurn[]>([]), threadId = ref(''), historyError = ref('')
  async function hydrate() {
    if (!threadId.value) return
    const transcript = await conversationTranscript(threadId.value)
    turns.value = transcript.items.map(item => {
      const turn = makeTurn(item.client_message_id, item.message ?? '此轮内容当前不可访问')
      turn.withheld = item.content_access === 'withheld'
      if (item.response) apply(turn, item.response)
      else if (!turn.withheld) turn.status = '该消息尚未完成，使用重试继续处理。'
      return turn
    })
  }
  onMounted(async () => {
    try { const list = await listConversations(); threadId.value = list.items[0]?.thread_id ?? ''; await hydrate() }
    catch (cause) { historyError.value = errorMessage(cause) }
    finally { loading.value = false }
  })
  async function clear() {
    if (loading.value) return
    loading.value = true
    try { threadId.value = (await createConversation()).thread_id; turns.value = []; historyError.value = '' }
    catch (cause) { historyError.value = errorMessage(cause) }
    finally { loading.value = false }
  }
  async function execute(turn: ChatTurn) {
    loading.value = true; turn.pending = true; turn.error = ''; turn.draft = ''; turn.steps = []
    try {
      await sendChatMessage(threadId.value, turn.question, turn.id, event => {
        if (event.type === 'status') { turn.status = event.message; if (event.reset_draft) turn.draft = ''; if (!turn.steps.includes(event.message)) turn.steps.push(event.message) }
        if (event.type === 'token') turn.draft += event.text
        if (event.type === 'result') apply(turn, event.data)
      })
    } catch (cause) { turn.error = errorMessage(cause); turn.draft = '' }
    finally { turn.pending = false; loading.value = false }
  }
  async function submit() {
    const text = question.value.trim()
    if (!text || loading.value) return
    if (!threadId.value) { await clear(); if (!threadId.value) return }
    const turn = makeTurn(crypto.randomUUID(), text)
    turns.value.push(turn); question.value = ''
    await execute(turns.value[turns.value.length - 1])
  }
  async function retry(turn: ChatTurn) { if (!loading.value && !turn.withheld) await execute(turn) }
  return { question, loading, turns, threadId, historyError, submit, clear, retry }
}
