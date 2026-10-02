import { ref } from 'vue'
import type { ChatAskResponse } from '../types/chat'

export interface ChatTurn {
  id: number
  query: string
  response: ChatAskResponse | null
  error: string
  timestamp: number
}

const turns = ref<ChatTurn[]>([])
let nextId = 0

export function useChatHistory() {
  function addTurn(query: string, response: ChatAskResponse | null, error: string = '') {
    turns.value.push({
      id: nextId++,
      query,
      response,
      error,
      timestamp: Date.now(),
    })
  }

  function clearHistory() {
    turns.value = []
  }

  function lastTurn(): ChatTurn | null {
    return turns.value.length > 0 ? turns.value[turns.value.length - 1] : null
  }

  return { turns, addTurn, clearHistory, lastTurn }
}