import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import path from 'path'
import { viteStaticCopy } from 'vite-plugin-static-copy'

const BACKEND = process.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default defineConfig({
  plugins: [
    react(),
    viteStaticCopy({
      targets: [
        {
          // pdfjs-dist is pinned to 4.8.69 (exact) in package.json to match
          // react-pdf's bundled pdfjs API; npm dedupes it to the top level.
          // Copy THAT worker to /pdf.worker.mjs so PlanViewer and the annotator
          // load one worker whose version matches the API. If pdfjs-dist is
          // ever allowed to float (^) again it drifts (e.g. 4.10.38) and every
          // PDF load fails with "Nepavyko atidaryti PDF" / a version-mismatch
          // warning — keep it pinned to react-pdf's pdfjs version.
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
    // Playwright writes trace snapshots (.html) into e2e/.results while a test runs; watched, each one made
    // Vite reload every open page mid-test (seen 2026-10-19: „page reload e2e/.results/…/traces/…html").
    watch: { ignored: ['**/e2e/.results/**', '**/e2e/.state/**'] },
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
      // Viewer calibration pre-fill (main.py /detect-scale-hint) — the route
      // existed but was missing here, so it 404'd in dev. (2026-07-28.)
      '/detect-scale-hint': { target: BACKEND, changeOrigin: true },
      '/api':              { target: BACKEND, changeOrigin: true },
      '/v9':               { target: BACKEND, changeOrigin: true },
    },
  },
})
