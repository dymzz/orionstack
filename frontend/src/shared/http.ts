// The HttpOnly session is managed by the browser. CSRF is not an identity credential.
let csrfToken: string | null = null
export function setCsrfToken(value: string | null) { csrfToken = value }

const DEFAULT_TIMEOUT_MS = 30_000
const CHAT_TIMEOUT_MS = 60_000

export class ApiError extends Error {
  constructor(public status: number, body: string, public requestId: string | null = null) { super(body || `Request failed: ${status}`) }
}

export function errorMessage(error: unknown): string {
  const text = baseErrorMessage(error)
  return error instanceof ApiError && error.requestId ? `${text} 请求 ID：${error.requestId}` : text
}

function baseErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return '登录已失效，请重新登录。'
    if (error.status === 403) return '当前账号没有此操作权限。'
    if (error.status === 404) return '请求的资源或版本当前不可用。'
    if (error.status === 409) return '文档版本已变化，请刷新后重试。'
    if (error.status === 503) return '核心服务依赖暂不可用，请稍后重试。'
    if (error.status === 400 || error.status === 422) return '输入或文件格式不符合要求，请检查后重试。'
  }
  if (error instanceof Error && error.message === 'Request timed out') return '请求超时，请刷新确认当前状态。'
  return '请求失败，请检查服务连接后重试。'
}

function createAbortController(timeoutMs: number): { signal: AbortSignal; clear: () => void } {
  const controller = new AbortController()
  const id = setTimeout(() => controller.abort(), timeoutMs)
  return { signal: controller.signal, clear: () => clearTimeout(id) }
}

export async function getJson<T>(url: string, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const { signal, clear } = createAbortController(timeoutMs)
  try {
    const response = await fetch(url, {
      headers: buildAuthHeaders(),
      signal,
    })

    if (!response.ok) {
      handleAuthFailure(response)
      const text = await response.text()
      throw new ApiError(response.status, text, response.headers.get('X-Core-Request-ID') ?? response.headers.get('X-Request-ID'))
    }

    return (await response.json()) as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Request timed out')
    }
    throw error
  } finally {
    clear()
  }
}

export async function postJson<T>(url: string, body: unknown, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const { signal, clear } = createAbortController(timeoutMs)
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...buildAuthHeaders(),
      },
      body: JSON.stringify(body),
      signal,
    })

    if (!response.ok) {
      handleAuthFailure(response)
      const text = await response.text()
      throw new ApiError(response.status, text, response.headers.get('X-Core-Request-ID') ?? response.headers.get('X-Request-ID'))
    }

    return (await response.json()) as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Request timed out')
    }
    throw error
  } finally {
    clear()
  }
}

export async function deleteJson<T>(url: string, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const { signal, clear } = createAbortController(timeoutMs)
  try {
    const response = await fetch(url, {
      method: 'DELETE',
      headers: buildAuthHeaders(),
      signal,
    })

    if (!response.ok) {
      handleAuthFailure(response)
      const text = await response.text()
      throw new ApiError(response.status, text, response.headers.get('X-Core-Request-ID') ?? response.headers.get('X-Request-ID'))
    }

    return (await response.json()) as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Request timed out')
    }
    throw error
  } finally {
    clear()
  }
}

function buildAuthHeaders(): Record<string, string> {
  return csrfToken ? { 'X-CSRF-Token': csrfToken } : {}
}

function handleAuthFailure(response: Response) {
  if (response.status !== 401) return
  csrfToken = null
  window.dispatchEvent(new CustomEvent('orionstack-auth-expired'))
}

export { DEFAULT_TIMEOUT_MS, CHAT_TIMEOUT_MS }

export async function postForm<T>(url: string, body: FormData, timeoutMs = 180_000): Promise<T> {
  const { signal, clear } = createAbortController(timeoutMs)
  try {
    const response = await fetch(url, { method: 'POST', headers: buildAuthHeaders(), body, signal })
    if (!response.ok) { handleAuthFailure(response); throw new ApiError(response.status, await response.text(), response.headers.get('X-Core-Request-ID') ?? response.headers.get('X-Request-ID')) }
    return await response.json() as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new Error('Request timed out')
    throw error
  } finally { clear() }
}

export async function downloadFile(url: string, filename: string) {
  const { signal, clear } = createAbortController(DEFAULT_TIMEOUT_MS)
  let objectUrl: string | undefined
  try {
    const response = await fetch(url, { headers: buildAuthHeaders(), signal })
    if (!response.ok) { handleAuthFailure(response); throw new ApiError(response.status, await response.text(), response.headers.get('X-Core-Request-ID') ?? response.headers.get('X-Request-ID')) }
    objectUrl = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = objectUrl; link.download = filename; link.click()
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new Error('Request timed out')
    throw error
  } finally { clear(); if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl!), 1000) }
}

export async function postEventStream(url: string, body: unknown, onEvent: (event: any) => void) {
  const { signal, clear } = createAbortController(180_000)
  try {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...buildAuthHeaders() }, body: JSON.stringify(body), signal })
    if (!response.ok) { handleAuthFailure(response); throw new ApiError(response.status, await response.text()) }
    if (!response.body || !response.headers.get('Content-Type')?.startsWith('text/event-stream')) throw new Error('Invalid chat stream')
    const reader = response.body.getReader(), decoder = new TextDecoder()
    let buffer = '', finished = false
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
      if (buffer.length > 2_000_000) throw new Error('Chat stream too large')
      let index: number
      while ((index = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, index); buffer = buffer.slice(index + 2)
        const data = block.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n')
        if (!data) continue
        const event = JSON.parse(data)
        if (event.type === 'error') throw new Error('Chat stream interrupted')
        if (event.type === 'result') finished = true
        onEvent(event)
      }
      if (done) break
    }
    if (!finished) throw new Error('Chat stream interrupted')
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new Error('Request timed out')
    throw error
  } finally { clear() }
}
