import { computed, readonly, ref } from 'vue'
import { errorMessage, getJson, postJson, setCsrfToken } from '../../shared/http'
import type { AccessContext } from './types'
export interface IdentityConfig { mode: 'oidc' | 'demo'; login_url: string | null }
interface SessionResponse {
  authenticated: boolean; principal_id: string; username: string; role: string
  authentication: 'oidc' | 'demo'; csrf_token: string; expires_at: string
}
const authenticated = ref(false)
const currentUsername = ref<string | null>(null)
const currentRole = ref<string | null>(null)
const principalId = ref<string | null>(null)
const authentication = ref<'oidc' | 'demo' | null>(null)
const accessContext = ref<AccessContext | null>(null)
const accessError = ref('')
const permissions = computed(() => accessContext.value?.permissions)
function clearSession() {
  authenticated.value = false; currentUsername.value = null; currentRole.value = null
  principalId.value = null; authentication.value = null; accessContext.value = null; setCsrfToken(null)
}
window.addEventListener('orionstack-auth-expired', clearSession)
export function useAuthState() {
  return { authenticated: readonly(authenticated), currentUsername: readonly(currentUsername),
    currentRole: readonly(currentRole), principalId: readonly(principalId), authentication: readonly(authentication),
    accessContext: readonly(accessContext), accessError: readonly(accessError), permissions }
}
export function isAuthenticated() { return authenticated.value }
export function isAdmin() { return currentRole.value === 'admin' }
export function getIdentityConfig() { return getJson<IdentityConfig>('/api/auth/config') }
export function beginOidcLogin(returnTo: string) {
  const path = returnTo.startsWith('/') && !returnTo.startsWith('//') && !returnTo.includes('\\') ? returnTo : '/'
  window.location.assign('/api/auth/start?return_to=' + encodeURIComponent(path))
}
// Only the explicitly selected local demo uses a local form.
export async function login(username: string, password: string) {
  await postJson('/api/auth/demo-login', { username, password })
  return refreshAuthStatus()
}
export async function refreshAuthStatus() {
  try {
    const response = await getJson<SessionResponse>('/api/auth/session')
    authenticated.value = response.authenticated; currentUsername.value = response.username
    currentRole.value = response.role; principalId.value = response.principal_id
    authentication.value = response.authentication; setCsrfToken(response.csrf_token)
    accessContext.value = null; accessError.value = ''
    if (response.authenticated) {
      try { accessContext.value = await getJson<AccessContext>('/api/access-context') }
      catch (error) { accessError.value = errorMessage(error) }
    }
    return response.authenticated
  } catch { clearSession(); return false }
}
export async function logout() {
  // Keep the visible session if the server failed to revoke it.
  await postJson('/api/auth/logout', {})
  clearSession()
}
