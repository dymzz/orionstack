export const logRoutes = [{ path: '/logs/:view?', name: 'logs', component: () => import('./pages/LogsPage.vue'), meta: { requiresAuth: true } }]
