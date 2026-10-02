export const AUTH_TOKEN_STORAGE_KEY = 'orionstack_auth_token'

const DEFAULT_TIMEOUT_MS = 30_000
const CHAT_TIMEOUT_MS = 60_000

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
      throw new Error(text || `Request failed: ${response.status}`)
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
      throw new Error(text || `Request failed: ${response.status}`)
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
      throw new Error(text || `Request failed: ${response.status}`)
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
  const token = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function handleAuthFailure(response: Response) {
  if (response.status !== 401) return
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
  window.localStorage.removeItem('orionstack_username')
  window.localStorage.removeItem('orionstack_role')
  window.dispatchEvent(new CustomEvent('orionstack-auth-expired'))
}

export { DEFAULT_TIMEOUT_MS, CHAT_TIMEOUT_MS }