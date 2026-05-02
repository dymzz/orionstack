export const AUTH_TOKEN_STORAGE_KEY = 'orionstack_admin_token'

export async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: buildAuthHeaders(),
  })

  if (!response.ok) {
    handleAuthFailure(response)
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }

  return (await response.json()) as T
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    handleAuthFailure(response)
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }

  return (await response.json()) as T
}

function buildAuthHeaders(): Record<string, string> {
  const token = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function handleAuthFailure(response: Response) {
  if (response.status !== 401) return
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
  window.dispatchEvent(new CustomEvent('orionstack-auth-expired'))
}
