import { createRouter, createWebHistory } from 'vue-router'
import { accountRoutes, isAuthenticated, isAdmin, refreshAuthStatus } from './modules/account'
import { qaRoutes } from './modules/qa'
import { dataRoutes } from './modules/data-ops'
import { logRoutes } from './modules/logs'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'workbench', component: () => import('./compositions/Workbench.vue'), meta: { requiresAuth: true } },
    ...accountRoutes, ...qaRoutes, ...dataRoutes, ...logRoutes,
    { path: '/admin/traces', redirect: '/logs/retrieval' },
    // Existing extraction/diagnostic tools remain separate from the new core UI.
    {
      path: '/admin', component: () => import('./pages/admin/AdminLayout.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
      children: [
        { path: '', redirect: '/admin/account' },
        { path: 'hard-cases', name: 'hard-cases', component: () => import('./pages/admin/HardCaseListPage.vue') },
        { path: 'extraction', name: 'extraction', component: () => import('./pages/admin/ExtractionReviewPage.vue') },
        { path: 'debug', name: 'debug', component: () => import('./pages/admin/AdminDebugPage.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
router.beforeEach(async to => {
  if (to.name === 'login') {
    if (await refreshAuthStatus()) return '/'
    return true
  }
  if (!to.matched.some(record => record.meta.requiresAuth)) return true
  if (!await refreshAuthStatus()) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.matched.some(record => record.meta.requiresAdmin) && !isAdmin()) return '/'
  return true
})
export default router
