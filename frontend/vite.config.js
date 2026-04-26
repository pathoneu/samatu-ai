import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import path from 'path'

const BACKEND = 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      '/extract-interior': { target: BACKEND, changeOrigin: true },
      '/chat-project':     { target: BACKEND, changeOrigin: true },
      '/pdf-lines':        { target: BACKEND, changeOrigin: true },
      '/extract-facade':   { target: BACKEND, changeOrigin: true },
      '/extract-roof':     { target: BACKEND, changeOrigin: true },
      '/extract-earthworks': { target: BACKEND, changeOrigin: true },
      '/extract-concrete': { target: BACKEND, changeOrigin: true },
      '^/extract$':        { target: BACKEND, changeOrigin: true },
      '/detect-type':      { target: BACKEND, changeOrigin: true },
      '/generate-excel':   { target: BACKEND, changeOrigin: true },
      '/generate-pdf':     { target: BACKEND, changeOrigin: true },
      '/export':           { target: BACKEND, changeOrigin: true },
      '/dev':              { target: BACKEND, changeOrigin: true },
      '/openapi.json':     { target: BACKEND, changeOrigin: true },
      '/health':           { target: BACKEND, changeOrigin: true },
    },
  },
})
