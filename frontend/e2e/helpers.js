/**
 * Page helpers for the founder-guide smoke suite. Canvas clicks are computed from the page element's box
 * (`div[data-page-number=N]`) and a point in the sheet's DISPLAY frame (the frame `polygon_pct` and `_vieta`
 * live in) — never hard-coded pixels.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, expect } from './pw.js';
import { PROJECT, START_JSON, fingerprint, getProject, readJson, restoreDb, restoreStore, START_DB } from './state.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const SCREENS = path.join(HERE, '__screens__');
export const PROJECT_URL = `/project/${PROJECT}`;
export const PYTHON_HELPER = path.join(HERE, 'make_revision.py');

/** Record a number the test asserted — the reporter prints them in one table at the end. */
export function note(text) {
  test.info().annotations.push({ type: 'asserted', description: text });
}

export async function shot(page, name) {
  fs.mkdirSync(SCREENS, { recursive: true });
  await page.screenshot({ path: path.join(SCREENS, `${name}.png`) });
}

export const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Put the database and pdf_store back to the guide's start state and prove it through the API. */
export async function restoreStart() {
  restoreDb(START_DB);
  restoreStore();
  const want = readJson(START_JSON);
  const got = fingerprint(await getProject());
  for (const k of Object.keys(got)) {
    if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) {
      throw new Error(`start state not restored: ${k} = ${JSON.stringify(got[k])}, want ${JSON.stringify(want[k])}`);
    }
  }
}

/**
 * The test's `page`, plus: every API write the page starts is tracked, and before the context closes the
 * fixture waits until none is in flight (and the 400 ms save debounce has had its chance) — so no write
 * of this test can land after the next test's restore.
 */
const GEOMETRY = new WeakMap();

export const it = test.extend({
  page: async ({ page }, use) => {
    const inflight = new Set();
    const geometry = new Set();
    GEOMETRY.set(page, geometry);
    page.on('response', (r) => {
      const m = /\/pages\/(\d+)\/geometry/.exec(r.url());
      if (m && r.ok()) geometry.add(Number(m[1]));
    });
    const isWrite = (r) => r.url().includes('/api/') && r.method() !== 'GET';
    page.on('request', (r) => { if (isWrite(r)) inflight.add(r); });
    page.on('requestfinished', (r) => inflight.delete(r));
    page.on('requestfailed', (r) => inflight.delete(r));
    await use(page);
    const t0 = Date.now();
    let quiet = Date.now();
    while (Date.now() - t0 < 20_000) {
      if (inflight.size) quiet = Date.now();
      else if (Date.now() - quiet > 1500) break;
      await new Promise((r) => setTimeout(r, 100));
    }
  },
});

/**
 * The sheet's wall geometry (snap targets) is fetched lazily when a tool is armed; a click before it
 * arrives does not snap. Arm „Atstumas" once if nothing has fetched it yet, wait, and leave the tool —
 * after that every tool on the sheet snaps the same way (lib/pageGeometryApi caches it per sheet).
 */
export async function loadGeometry(page, pageNr = 1) {
  const seen = GEOMETRY.get(page);
  if (!seen.has(pageNr)) {
    await page.getByRole('button', { name: 'Atstumas', exact: true }).click();
    await expect.poll(() => seen.has(pageNr), { timeout: 30_000 }).toBe(true);
    await page.keyboard.press('Escape');
  }
}

/** Opens the demo project. By default the first-run coach marks and the cookie banner are pre-answered. */
export async function openProject(page, { coach = false, cookie = false, suffix = '' } = {}) {
  await page.addInitScript(({ coach: c, cookie: k }) => {
    try {
      if (!c) localStorage.setItem('samatu_viewer_onboarded', '1');
      if (!k) {
        localStorage.setItem('pathon_cookie_consent', JSON.stringify({
          categories: { necessary: true, analytics: false, marketing: false }, timestamp: Date.now(),
        }));
      }
    } catch { /* storage blocked */ }
  }, { coach, cookie });
  await page.goto(`${PROJECT_URL}${suffix}`);
  if (!suffix) await viewerReady(page);
}

export async function viewerReady(page) {
  await expect(page.locator('div[data-page-number="1"]')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText('Kraunamas dokumentas', { exact: false })).toHaveCount(0, { timeout: 60_000 });
  await expect(page.getByRole('button', { name: /^Patalpos 11 / })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Kraunama...', { exact: true })).toHaveCount(0);
}

/** The room's row in the right panel's list. */
export function roomRow(page, nr) {
  return page.locator('[title^="Atidaryti psl."]').filter({ has: page.getByText(nr, { exact: true }) });
}

/** A row of the right panel's „Matavimai" list (its label and value sit in separate elements). */
export function measRow(page, label, value) {
  return page.locator('div')
    .filter({ has: page.getByText(label, { exact: true }) })
    .filter({ has: page.getByText(value, { exact: true }) })
    .last();
}

/** Focus a room via its list row — the room tools appear only then. */
export async function focusRoom(page, nr) {
  await roomRow(page, nr).click();
  await expect(page.getByTestId('outline-edit-start')).toBeVisible();
  await expect(page.getByTestId('outline-tool-buttons')).toBeVisible();
}

async function stableBox(locator) {
  let prev = null;
  for (let i = 0; i < 40; i++) {
    const b = await locator.boundingBox();
    if (b && prev && Math.abs(b.x - prev.x) < 0.5 && Math.abs(b.y - prev.y) < 0.5 && Math.abs(b.width - prev.width) < 0.5) return b;
    prev = b;
    await new Promise((r) => setTimeout(r, 100));
  }
  return prev;
}

/**
 * Scroll the viewer so the centre of `pts` (sheet display-frame fractions) sits in the middle of the
 * scroller, and return their screen points. Each point must land on the page itself (no panel over it).
 */
export async function sheetPoints(page, pageNr, pts) {
  const pg = page.locator(`div[data-page-number="${pageNr}"]`);
  await pg.waitFor({ state: 'attached' });
  const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length;
  const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  await pg.evaluate((el, [fx, fy]) => {
    let s = el.parentElement;
    while (s && !(s.scrollHeight > s.clientHeight + 10 && /(auto|scroll)/.test(getComputedStyle(s).overflowY))) s = s.parentElement;
    if (!s) return;
    const r = el.getBoundingClientRect();
    const sr = s.getBoundingClientRect();
    s.scrollBy({ left: r.left + fx * r.width - (sr.left + sr.width / 2), top: r.top + fy * r.height - (sr.top + sr.height / 2), behavior: 'instant' });
  }, [cx, cy]);
  const b = await stableBox(pg);
  const out = pts.map(([fx, fy]) => ({ x: b.x + fx * b.width, y: b.y + fy * b.height }));
  const onPage = await page.evaluate(({ pts: ps, n }) => ps.map(({ x, y }) => {
    const el = document.elementFromPoint(x, y);
    return !!el?.closest?.(`[data-page-number="${n}"]`);
  }), { pts: out, n: pageNr });
  onPage.forEach((ok, i) => {
    if (!ok) throw new Error(`sheet ${pageNr} point ${pts[i]} is not visible on the page (covered or scrolled away)`);
  });
  return out;
}

/** A click that first moves there (snapping and hover markers react to the move). */
export async function clickAt(page, { x, y }, opts = {}) {
  await page.mouse.move(x, y, { steps: 5 });
  await page.waitForTimeout(80);
  await page.mouse.down(opts);
  await page.mouse.up(opts);
  await page.waitForTimeout(150);
}

export async function dragBetween(page, a, b) {
  await page.mouse.move(a.x, a.y, { steps: 4 });
  await page.mouse.down();
  await page.mouse.move(b.x, b.y, { steps: 14 });
  await page.mouse.up();
  await page.waitForTimeout(200);
}

/** A sonner toast with this text (toasts auto-dismiss — assert right after the action). */
export function toast(page, text) {
  return page.locator('[data-sonner-toast]').filter({ hasText: text });
}

/** The quantity of a priced row as the „Kiekiai" tab prints it (accessible name ends with "<label> <qty>"). */
export function kiekiaiRow(page, label, qty) {
  return page.getByRole('treeitem', { name: new RegExp(`${escapeRe(label)} ${escapeRe(qty)}$`) });
}

export async function expectKiekiai(page, rows) {
  await page.getByRole('tab', { name: 'Kiekiai' }).click();
  for (const [label, qty] of rows) await expect(kiekiaiRow(page, label, qty)).toBeVisible();
  await page.getByRole('tab', { name: 'Patalpos ir eilutės' }).click();
}

export function centroid(ring) {
  let a = 0; let x = 0; let y = 0;
  for (let i = 0; i < ring.length; i++) {
    const [x0, y0] = ring[i];
    const [x1, y1] = ring[(i + 1) % ring.length];
    const f = x0 * y1 - x1 * y0;
    a += f; x += (x0 + x1) * f; y += (y0 + y1) * f;
  }
  return a ? [x / (3 * a), y / (3 * a)] : [ring.reduce((s, p) => s + p[0], 0) / ring.length, ring.reduce((s, p) => s + p[1], 0) / ring.length];
}

export function insidePolygon([px, py], ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export const lt = (n, d = 2) => n.toLocaleString('lt-LT', { minimumFractionDigits: d, maximumFractionDigits: d });
