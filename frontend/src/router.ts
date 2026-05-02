import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated, refreshAuthStatus } from './services/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: () => import('./pages/chat/ChatPage.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('./pages/LoginPage.vue'),
    },
    {
      path: '/admin',
      component: () => import('./pages/admin/AdminLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'admin',
          redirect: '/admin/traces',
        },
        {
          path: 'traces',
          name: 'traces',
          component: () => import('./pages/admin/TraceListPage.vue'),
        },
        {
          path: 'hard-cases',
          name: 'hard-cases',
          component: () => import('./pages/admin/HardCaseListPage.vue'),
        },
        {
          path: 'extraction',
          name: 'extraction',
          component: () => import('./pages/admin/ExtractionReviewPage.vue'),
        },
        {
          path: 'debug',
          name: 'debug',
          component: () => import('./pages/admin/AdminDebugPage.vue'),
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  if (to.name === 'login' && isAuthenticated()) {
    return '/admin/traces'
  }

  if (!to.matched.some((record) => record.meta.requiresAuth)) {
    return true
  }

  const authenticated = await refreshAuthStatus()
  if (authenticated) {
    return true
  }

  return {
    name: 'login',
    query: { redirect: to.fullPath },
  }
})

export default router
