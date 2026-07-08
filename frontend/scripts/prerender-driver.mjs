/**
 * prerender-driver.mjs — renders routes in headless chromium and saves the
 * serialized DOM into dist/<route>/index.html. Do not run directly; it is
 * invoked by scripts/prerender.mjs UNDER
 *   npm exec --package=playwright@1.55.1 -- node scripts/prerender-driver.mjs …
 * so the pinned playwright (with its chromium cached in
 * ~/Library/Caches/ms-playwright) is available WITHOUT being a dependency of
 * this app (same decision as og-shot.mjs).
 *
 * npm exec only prepends the staged package's node_modules/.bin to PATH — it
 * does not make `import 'playwright'` resolvable from this project. So we
 * resolve it manually: find the …/node_modules/.bin PATH entry npm added and
 * require('playwright') from its parent node_modules.
 */
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

function loadPlaywright() {
  // Direct resolution first — works if playwright ever becomes a real dep.
  try {
    return createRequire(import.meta.url)('playwright');
  } catch {
    /* expected: not a project dependency */
  }
  for (const bin of (process.env.PATH ?? '').split(path.delimiter)) {
    if (!bin.endsWith(path.join('node_modules', '.bin'))) continue;
    try {
      return createRequire(path.join(bin, '..', 'probe.js'))('playwright');
    } catch {
      /* keep scanning */
    }
  }
  throw new Error(
    'playwright is not resolvable. Run via scripts/prerender.mjs (npm run build:seo), ' +
    'which wraps this driver in `npm exec --package=playwright@1.55.1`.',
  );
}

const [origin, distDir, ...routes] = process.argv.slice(2);
if (!origin || !distDir || routes.length === 0) {
  console.error('usage: node scripts/prerender-driver.mjs <origin> <distDir> <route…>');
  process.exit(2);
}

const { chromium } = loadPlaywright();

let browser;
try {
  browser = await chromium.launch();
} catch (err) {
  console.error(err.message);
  console.error('\nChromium build missing? Cache it once with:\n  npx -y playwright@1.55.1 install chromium');
  process.exit(1);
}

try {
  const page = await browser.newPage();
  // Deterministically ANONYMOUS: block every /api/* call. vite preview
  // inherits the dev server proxy, so if the auth-disabled dev backend is up,
  // /api/auth/me would auto-log-in the driver and "/" would prerender the
  // DASHBOARD instead of the landing (2026-07-08 trap). Aborted auth = user
  // null = public pages, regardless of what's running on :8000.
  await page.route('**/api/**', (r) => r.abort());
  // Two passes on purpose: capture everything FIRST, write files at the END.
  // dist/index.html doubles as the preview server's SPA fallback — overwriting
  // it mid-run would make every later route render on top of the already-
  // prerendered "/" document (leaked <head> stamps/meta) instead of the
  // virgin shell.
  const rendered = [];
  for (const route of routes) {
    await page.goto(new URL(route, origin).href, { waitUntil: 'networkidle', timeout: 45_000 });
    // Lazy routes mount through Suspense — the page is real once its h1 lands.
    await page.waitForSelector('h1', { timeout: 15_000 });
    // Scroll-reveal settle: under webdriver the app reveals ALL [data-reveal]
    // content immediately, but on /en that happens across a language-flip
    // re-render — a fixed sleep raced it (2026-07-08: /en captured with 1/42
    // revealed). Wait for the invariant instead: no unrevealed elements left
    // (vacuously true for routes without reveals).
    await page
      .waitForFunction(
        () => document.querySelectorAll('[data-reveal]:not(.plin)').length === 0,
        { timeout: 5_000 },
      )
      .catch(() => console.warn(`  ! ${route}: unrevealed [data-reveal] content at capture time`));
    await page.waitForTimeout(400); // let mount effects (title/meta/JSON-LD) settle
    let html = await page.content();
    // Stamp so "is prod actually serving prerendered HTML?" is a one-grep check.
    html = html.replace(
      '<head>',
      `<head><!-- prerendered ${route} ${new Date().toISOString().slice(0, 10)} -->`,
    );
    rendered.push({ route, html });
  }
  for (const { route, html } of rendered) {
    const outDir = path.join(distDir, ...route.split('/').filter(Boolean));
    await mkdir(outDir, { recursive: true });
    const outFile = path.join(outDir, 'index.html');
    await writeFile(outFile, html, 'utf8');
    console.log(`  ✓ ${route.padEnd(26)} → ${outFile} (${Math.round(html.length / 1024)} kB)`);
  }
} finally {
  await browser.close();
}
