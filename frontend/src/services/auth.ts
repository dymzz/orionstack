import { readonly, ref } from 'vue'
import { AUTH_TOKEN_STORAGE_KEY, getJson, postJson } from './api'

interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  username: string
  role: string
}

interface AuthStatusResponse {
  authenticated: boolean
  username?: string | null
  role?: string | null
}

const authenticated = ref(Boolean(window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)))
const currentUsername = ref<string | null>(window.localStorage.getItem('orionstack_username'))
const currentRole = ref<string | null>(window.localStorage.getItem('orionstack_role'))

window.addEventListener('orionstack-auth-expired', () => {
  authenticated.value = false
  currentUsername.value = null
  currentRole.value = null
})

export function useAuthState() {
  return {
    authenticated: readonly(authenticated),
    currentUsername: readonly(currentUsername),
    currentRole: readonly(currentRole),
  }
}

export function isAuthenticated() {
  return authenticated.value
}

export function isAdmin() {
  return currentRole.value === 'admin'
}

export async function login(username: string, password: string) {
  const response = await postJson<LoginResponse>('/api/v1/auth/login', { username, password })
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, response.access_token)
  window.localStorage.setItem('orionstack_username', response.username)
  window.localStorage.setItem('orionstack_role', response.role)
  authenticated.value = true
  currentUsername.value = response.username
  currentRole.value = response.role
}

export async function refreshAuthStatus() {
  if (!window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)) {
    authenticated.value = false
    currentUsername.value = null
    currentRole.value = null
    return false
  }

  try {
    const response = await getJson<AuthStatusResponse>('/api/v1/auth/me')
    authenticated.value = response.authenticated
    currentUsername.value = response.username ?? null
    currentRole.value = response.role ?? null
    return response.authenticated
  } catch {
    authenticated.value = false
    currentUsername.value = null
    currentRole.value = null
    return false
  }
}

export async function logout() {
  try {
    if (window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)) {
      await postJson('/api/v1/auth/logout', {})
    }
  } finally {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
    window.localStorage.removeItem('orionstack_username')
    window.localStorage.removeItem('orionstack_role')
    authenticated.value = false
    currentUsername.value = null
    currentRole.value = null
  }
}