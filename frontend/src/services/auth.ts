import { readonly, ref } from 'vue'
import { AUTH_TOKEN_STORAGE_KEY, getJson, postJson } from './api'

interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  username: string
}

interface AuthStatusResponse {
  authenticated: boolean
  username?: string | null
}

const authenticated = ref(Boolean(window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)))
const currentUsername = ref<string | null>(window.localStorage.getItem('orionstack_admin_username'))

window.addEventListener('orionstack-auth-expired', () => {
  authenticated.value = false
  currentUsername.value = null
})

export function useAuthState() {
  return {
    authenticated: readonly(authenticated),
    currentUsername: readonly(currentUsername),
  }
}

export function isAuthenticated() {
  return authenticated.value
}

export async function login(username: string, password: string) {
  const response = await postJson<LoginResponse>('/api/auth/login', { username, password })
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, response.access_token)
  window.localStorage.setItem('orionstack_admin_username', response.username)
  authenticated.value = true
  currentUsername.value = response.username
}

export async function refreshAuthStatus() {
  if (!window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)) {
    authenticated.value = false
    currentUsername.value = null
    return false
  }

  try {
    const response = await getJson<AuthStatusResponse>('/api/auth/me')
    authenticated.value = response.authenticated
    currentUsername.value = response.username ?? null
    return response.authenticated
  } catch {
    authenticated.value = false
    currentUsername.value = null
    return false
  }
}

export async function logout() {
  try {
    if (window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)) {
      await postJson('/api/auth/logout', {})
    }
  } finally {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
    window.localStorage.removeItem('orionstack_admin_username')
    authenticated.value = false
    currentUsername.value = null
  }
}
