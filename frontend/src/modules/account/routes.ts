export const accountRoutes = [
  { path: '/login', name: 'login', component: () => import('./pages/LoginPage.vue') },
  { path: '/account', redirect: '/admin/account' },
  { path: '/admin/account', name: 'account', component: () => import('./pages/AccountPage.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
]
