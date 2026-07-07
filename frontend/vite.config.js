import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth':          { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health':        { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/tables':        { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/schema-tables': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/records':       { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/rebuild':       { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ask':           { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/write':         { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/erp':           { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/intent':        { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/crm':           { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})