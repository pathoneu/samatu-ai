/**
 * Safari robustness (Pathon v3, polish wave B1-A, 2026-10-19). Runs in chromium AND webkit
 * (playwright.config.js › projects). The founder walked togal-v2 on Safari and saw raw translation keys
 * („project.sanity.pillWarnings", „project.mainView.beVat"…) wherever a component used t(), and WebKit
 * logged `QuotaExceededError` on every project-cache write.
 *
 *  1. no translation key reaches the screen on Brėžinys, Patikra and Sąmata;
 *  2. a SECOND copy of react-i18next in the page — what a Vite dev server whose optimised-deps cache was
 *     rewritten under it serves, the shared node_modules/.vite trap — still translates (the components'
 *     useTranslation carries our i18next instance, lib i18n/react.js);
 *  3. a 6 MB project cache (more than Safari's ~5 MB): no refused write, no „atmintis pilna" toast, and the
 *     cache never keeps a copy older than the one this page saved;
 *  4. localStorage blocked outright (Safari „Block all cookies") — the workspace still opens.
 * Reads only: no test here saves to the project on purpose (the fixture still waits out stray writes).
 */
import { expect } from './pw.js';
import { it as test, openProject, restoreStart, viewerReady } from './helpers.js';
import { PROJECT_URL } from './helpers.js';

test.describe.configure({ mode: 'default' });
test.beforeEach(async () => { await restoreStart(); });

const KEY_RE = /\b(nav|lang|landing|pricing|login|authEmail|register|cookie|layout|dashboard|settings|project|shared|workspace|admin|newProject|runTeaching|upload|billing|usageMeter|priceLists|legal)\.[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)*\b/g;
const STEP_NAV = 'nav[aria-label="Projekto žingsniai"]';

/** Every key-shaped string on screen: visible text plus title / aria-label / placeholder attributes. */
async function rawKeys(page) {
  const text = await page.evaluate(() => [
    document.body.innerText,
    ...Array.from(document.querySelectorAll('[title],[aria-label],[placeholder]'))
      .map((e) => [e.getAttribute('title'), e.getAttribute('aria-label'), e.getAttribute('placeholder')].join(' ')),
  ].join('\n'));
  // e-mail addresses and file names are not keys
  return [...new Set((text.match(KEY_RE) || []).filter((k) => !/\.(pdf|png|jpg|xlsx|csv|json|eu|lt|com)$/i.test(k)))];
}

async function goToStep(page, label) {
  await page.locator(`${STEP_NAV} button`, { hasText: label }).first().click();
  await page.waitForTimeout(1500);
}

test('1 no translation key on screen — Brėžinys, Patikra, Sąmata', async ({ page }) => {
  const refused = [];
  page.on('console', (m) => { if (/localStorage write failed/.test(m.text())) refused.push(m.text()); });
  await openProject(page);
  expect(await rawKeys(page), 'Brėžinys').toEqual([]);
  // the plain demo project in a fresh profile: WebKit refused every cache write and toasted „atmintis pilna"
  expect(refused, 'no refused localStorage write').toEqual([]);
  await expect(page.getByText('Naršyklės atmintis pilna', { exact: false })).toHaveCount(0);
  await goToStep(page, 'Patikra');
  expect(await rawKeys(page), 'Patikra').toEqual([]);
  await goToStep(page, 'Sąmata');
  expect(await rawKeys(page), 'Sąmata').toEqual([]);
});

test('2 a second copy of react-i18next in the page still translates', async ({ page }) => {
  // Every app module except the one that runs initReactI18next imports react-i18next under ANOTHER URL — the
  // browser evaluates it as a second module whose registered instance is empty. Without the explicit
  // instance, react-i18next returns the key as the text: the founder's Safari screen.
  const rewritten = new Set();
  await page.route(/\/src\/.+\.(jsx?|tsx?)(\?.*)?$/, async (route) => {
    const url = route.request().url();
    if (/\/src\/i18n\/index\.js/.test(url)) return route.continue();
    const res = await route.fetch();
    const body = await res.text();
    const next = body.replace(/(react-i18next\.js\?v=[\w]+)/g, '$1&copy=2');
    if (next !== body) rewritten.add(url.replace(/^.*\/src\//, 'src/'));
    return route.fulfill({ response: res, body: next });
  });
  await openProject(page);
  expect(rewritten.size, 'the second copy was actually served').toBeGreaterThan(0);
  const copies = await page.evaluate(() => performance.getEntriesByType('resource')
    .map((e) => e.name).filter((n) => /react-i18next\.js/.test(n)));
  expect(new Set(copies.map((n) => n.includes('copy=2'))).size, 'both copies loaded').toBe(2);
  expect(await rawKeys(page)).toEqual([]);
  await expect(page.getByText('Be PVM', { exact: false }).first()).toBeAttached();
});

test('3 a 6 MB project cache: no refused write, no warning, never an older copy', async ({ page, browserName }) => {
  const refused = [];
  page.on('console', (m) => { if (/localStorage write failed/.test(m.text())) refused.push(m.text()); });
  // Fill the cache the way a long-used Safari profile has it: older projects, as much as the browser takes.
  await page.goto('/');
  const seeded = await page.evaluate(() => {
    const old = [];
    const pad = 'x'.repeat(380_000);
    for (let i = 0; i < 16; i += 1) {
      old.push({ id: `old-${i}`, name: `Senas ${i}`, updated_at: `2026-0${1 + (i % 8)}-01T10:00:00Z`, pad });
    }
    // as much of it as this browser takes (WebKit stops near 2,5 M characters, chromium near 5 M)
    let n = old.length;
    for (; n > 0; n -= 1) {
      try { localStorage.setItem('samatu_projects', JSON.stringify(old.slice(0, n))); break; } catch { /* smaller */ }
    }
    return { projects: n, chars: (localStorage.getItem('samatu_projects') || '').length };
  });
  expect(seeded.projects).toBeGreaterThan(0);
  await openProject(page);
  await page.waitForTimeout(2000);   // the 400 ms save debounce and the refresh write
  const server = await page.evaluate(async (url) => {
    const id = url.split('/').pop();
    const r = await fetch(`/api/projects/${id}`);
    return (await r.json()).updated_at;
  }, PROJECT_URL);
  const cache = await page.evaluate((url) => {
    const id = url.split('/').pop();
    const raw = localStorage.getItem('samatu_projects');
    const list = raw ? JSON.parse(raw) : [];
    const own = list.find((p) => p.id === id);
    return { count: list.length, has: !!own, updatedAt: own?.updated_at || null, chars: (raw || '').length };
  }, PROJECT_URL);
  test.info().annotations.push({ type: 'cache', description: `${browserName}: seeded ${seeded.projects} (${seeded.chars} ch) → cache ${cache.count} (${cache.chars} ch)` });
  expect(refused, 'no refused localStorage write').toEqual([]);
  await expect(page.getByText('Naršyklės atmintis pilna', { exact: false })).toHaveCount(0);
  // The cache holds the project as it is now — never the older copy a refused write would have kept.
  expect(cache.has).toBe(true);
  expect(cache.updatedAt >= server).toBe(true);
});

test('4 localStorage blocked outright — the workspace still opens', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() { throw new DOMException('The operation is insecure.', 'SecurityError'); },
    });
  });
  const crashes = [];
  page.on('pageerror', (e) => crashes.push(e.message));
  await page.goto(PROJECT_URL);
  const cookie = page.getByRole('button', { name: 'Tik būtinieji' });
  if (await cookie.isVisible({ timeout: 5000 }).catch(() => false)) await cookie.click();
  await viewerReady(page);
  await expect(page.getByText('Įvyko netikėta klaida', { exact: false })).toHaveCount(0);
  expect(crashes).toEqual([]);
  expect(await rawKeys(page)).toEqual([]);
});
