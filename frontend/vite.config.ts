import { defineConfig } from 'vite'
import { loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const backendOrigin = env.ORIONSTACK_BACKEND_ORIGIN || 'http://127.0.0.1:8000'

  return {
    plugins: [vue()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: backendOrigin,
          changeOrigin: true,
        },
        '/healthz': {
          target: backendOrigin,
          changeOrigin: true,
        },
      },
    },
  }
})
