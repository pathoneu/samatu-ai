#!/usr/bin/env node
/**
 * prerender.mjs — OPT-IN SEO build (`npm run build:seo`).
 *
 * Why: the site is a client-rendered SPA. Googlebot executes JS, but most AI
 * crawlers (and many scrapers) do NOT — they see an empty <div id="root">.
 * This script bakes each PUBLIC route's fully rendered HTML into
 * dist/<route>/index.html so raw-HTML crawlers get the real LT content,
 * per-route <title>/meta/canonical and the JSON-LD blocks.
 * (docs/marketing/seo-playbook.md §1 "Pending" item 1.)
 *
 * Flow: `vite build` → `vite preview` on :4517 → headless chromium renders
 * each route and the DOM is saved over/next to the SPA shell. The default
 * `npm run build` stays untouched (Render deploys use it).
 *
 * Playwright is NOT a dependency of this app (same decision as og-shot.mjs);
 * the driver runs under `npm exec --package=playwright@1.55.1` — pinned so it
 * reuses the chromium build already cached in ~/Library/Caches/ms-playwright.
 * First-ever run on a new machine: `npx -y playwright@1.55.1 install chromium`.
 *
 * The app hydrates normally on top of the prerendered HTML (React 18
 * createRoot re-renders #root), so real users are unaffected.
 */
import { spawn } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

// Public routes to prerender. Keep in sync with frontend/public/sitemap.xml
// and the public (non-ProtectedRoute) routes in src/App.jsx.
// /login and /register stay SPA-only on purpose: they are app chrome, and the
// prerendered "/" already carries the marketing head defaults.
const ROUTES = [
  '/',
  '/en',
  '/about',
  '/duk',
  '/privacy',
  '/terms',
  '/cookies',
  '/samatininko-kaina',
  '/kiekiai-is-brezinio',
  '/vidaus-apdailos-samata',
  '/apva-renovacijos-kiekiai',
];

const PORT = 4517;
const ORIGIN = `http://127.0.0.1:${PORT}`;
const PLAYWRIGHT_PKG = 'playwright@1.55.1'; // pinned — matches the cached chromium

function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: 'inherit' });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} ${args.join(' ')} exited with code ${code}`));
    });
  });
}

async function waitForServer(url, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`vite preview did not become ready at ${url} within ${timeoutMs} ms`);
}

console.log('[build:seo] 1/3 vite build');
await run('npm', ['run', 'build']);

console.log(`[build:seo] 2/3 vite preview on :${PORT} + prerender ${ROUTES.length} routes`);
const viteBin = path.join('node_modules', '.bin', 'vite');
const preview = spawn(viteBin, ['preview', '--port', String(PORT), '--strictPort'], {
  stdio: ['ignore', 'pipe', 'pipe'],
});
let previewLog = '';
preview.stdout.on('data', (d) => { previewLog += d; });
preview.stderr.on('data', (d) => { previewLog += d; });
const stopPreview = () => { if (preview.exitCode === null) preview.kill('SIGTERM'); };
process.on('exit', stopPreview);
process.on('SIGINT', () => process.exit(130));

try {
  await waitForServer(ORIGIN).catch((err) => {
    throw new Error(`${err.message}\n--- vite preview output ---\n${previewLog}`);
  });
  await run('npm', [
    'exec', '--yes', `--package=${PLAYWRIGHT_PKG}`, '--',
    'node', path.join('scripts', 'prerender-driver.mjs'), ORIGIN, 'dist', ...ROUTES,
  ]);
} finally {
  stopPreview();
}

console.log('[build:seo] 3/3 verify rendered output');
for (const route of ROUTES) {
  const file = path.join('dist', ...route.split('/').filter(Boolean), 'index.html');
  const html = await readFile(file, 'utf8');
  if (!html.includes('<h1')) {
    throw new Error(`${file}: no <h1> in prerendered HTML — route ${route} did not render`);
  }
}
console.log(`[build:seo] done — ${ROUTES.length} routes prerendered into dist/.`);
// NOTE: `vite preview` won't show these — its SPA fallback skips directory
// index files. Spot-check with a standard static server instead:
console.log('[build:seo] spot-check: `python3 -m http.server 8080 -d dist` then curl http://127.0.0.1:8080/duk/ | grep "prerendered"');
console.log('[build:seo] prod host must serve dist/<route>/index.html for extension-less URLs BEFORE the SPA fallback.');
