import { ref } from 'vue'

export interface ToastMessage {
  id: number
  text: string
  type: 'error' | 'success' | 'info'
}

const toasts = ref<ToastMessage[]>([])
let nextId = 0

export function useToast() {
  function show(text: string, type: ToastMessage['type'] = 'info', durationMs = 3000) {
    const id = nextId++
    toasts.value.push({ id, text, type })
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, durationMs)
  }

  function error(text: string) {
    show(text, 'error', 5000)
  }

  function success(text: string) {
    show(text, 'success', 3000)
  }

  function info(text: string) {
    show(text, 'info', 3000)
  }

  return { toasts, show, error, success, info }
}