import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 8801,
    proxy: {
      '/api': {
        target: 'http://localhost:8800',
        changeOrigin: true,
        cookieDomainRewrite: 'localhost',
        headers: { 'X-Frontend-Env': 'local' },
      },
      '/agent-api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/agent-api/, ''),
      },
    },
  },
})
