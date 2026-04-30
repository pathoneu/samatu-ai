import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import path from 'path'
import { viteStaticCopy } from 'vite-plugin-static-copy'

const BACKEND = 'http://localhost:8000';

export default defineConfig({
  plugins: [
    react(),
    viteStaticCopy({
      targets: [
        {
          src: 'node_modules/pdfjs-dist/build/pdf.worker.mjs',
          dest: '.',
          rename: 'pdf.worker.mjs',
        },
      ],
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // react-pdf + pdfjs-dist pulls ~600KB of WASM/PDF parsing — used
          // only on Brėžinys tab, lazy-load via separate chunk.
          'pdf-viewer': ['react-pdf', 'pdfjs-dist'],
          // Konva + react-konva — markup canvas, only loaded when PdfViewer
          // mounts.
          'canvas': ['konva', 'react-konva'],
        },
      },
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
      '/recompute-interior': { target: BACKEND, changeOrigin: true },
      '/api':              { target: BACKEND, changeOrigin: true },
      '/v9':               { target: BACKEND, changeOrigin: true },
    },
  },
})
