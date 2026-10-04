export const dataRoutes = [
  { path: '/data', name: 'dataops', component: () => import('./pages/DataOpsPage.vue'), meta: { requiresAuth: true } },
  { path: '/data/documents', redirect: '/data' },
  { path: '/data/storage', redirect: '/data' },
  { path: '/data/backups', redirect: '/data' },
  { path: '/support/diagnostics', name: 'diagnostics', component: () => import('./pages/DiagnosticsPage.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/admin/diagnostics', redirect: '/support/diagnostics' },
]
