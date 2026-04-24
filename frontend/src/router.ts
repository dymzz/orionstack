import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: () => import('./pages/chat/ChatPage.vue'),
    },
    {
      path: '/admin',
      component: () => import('./pages/admin/AdminLayout.vue'),
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

export default router
