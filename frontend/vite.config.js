import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // All API calls are proxied to FastAPI — no CORS issues in the browser
      '/auth':    { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health':  { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/tables':  { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/rebuild': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ask':     { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})