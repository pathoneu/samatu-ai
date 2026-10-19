/**
 * Room click, room tool, Undo, scale chip (Pathon v3, wave 1, track W1-D) on the demo project (demo-objektas_h).
 *
 *  - a click on a room on the drawing selects it, Shift+click adds one, empty paper clears (audit F1);
 *  - the room tool R: one click inside room 06 PROPOSES the wall-exact outline (nothing saved yet), Enter saves
 *    it — the saved outline is the very one the room sheet's „Parodyti patalpą" gives (≤ 0,5 % of the sheet
 *    per coordinate) — and „Atšaukti" in the toast puts the room back; inside room 04, which no wall separates
 *    from its neighbours, the tool says so;
 *  - „Sujungti" 04 + 05 → „Atšaukti" → 04 back to 26,31 m², 05 its own room again, journal rows `atsaukta`;
 *  - „Atimti" on 06 → „Atšaukti" → the hole is gone;
 *  - the scale chip: „1:115 · spėjamas" → one click „Patvirtinti" → „patvirtintas"; „Kalibruoti" arms the tool.
 *
 * WRITES to the project (outline saves, merges, a confirmed scale) — part of `npm run test:e2e`: every test
 * starts from the guide's start state (04 not merged, no scale confirmed) and the suite's teardown puts the
 * pristine database back. Other ports: E2E_BASE_URL / E2E_API_URL (W1-D: 5206 / 8126); backend with auth off.
 */
// Runs under the founder-guide suite's runner (npm run test:e2e): Playwright is resolved by ./pw.js, and the
// suite's global setup derives the guide's start state (.state/start.db) that every test here restores first
// (W0-A helpers: a SQLite-backup restore, proven through the API; the fixture waits for this test's writes).
import { expect } from './pw.js';
import { PROJECT, api } from './state.js';
import { clickAt, focusRoom, it, restoreStart, sheetPoints } from './helpers.js';

const test = it;

// Three points inside room 04 for a draft (W1-B's click-model spec uses the same) and a point inside room 06.
const DRAFT_04 = [[0.50, 0.52], [0.58, 0.52], [0.58, 0.60]];
const ROOM_06_INSIDE = [0.77, 0.40];

async function openProject(page) {
  await page.addInitScript(() => {
    try { localStorage.setItem('samatu_viewer_onboarded', '1'); } catch { /* private mode */ }
  });
  await page.goto(`/project/${PROJECT}`);
  const cookie = page.getByRole('button', { name: 'Tik būtinieji' });
  if (await cookie.isVisible({ timeout: 5000 }).catch(() => false)) await cookie.click();
  await expect(page.locator('[data-takeoff-viewer] [data-page-number="1"]')).toBeAttached({ timeout: 30_000 });
  await page.waitForTimeout(1500);
}

const sheet = (page) => page.evaluate(() => {
  const b = document.querySelector('[data-takeoff-viewer] [data-page-number="1"]').getBoundingClientRect();
  return { x: b.x, y: b.y, w: b.width, h: b.height };
});

/** Scroll the drawing so that the sheet-fraction height `fy` sits mid-canvas. */
async function bringIntoView(page, fy) {
  const canvas = await page.locator('[data-testid="viewer-canvas"]').boundingBox();
  const s = await sheet(page);
  const delta = s.y + fy * s.h - (canvas.y + canvas.height / 2);
  await page.mouse.move(canvas.x + canvas.width / 2, canvas.y + canvas.height / 2);
  if (Math.abs(delta) > 4) await page.mouse.wheel(0, delta);
  await page.waitForTimeout(600);
}

async function clickSheet(page, fx, fy, { shift = false } = {}) {
  const s = await sheet(page);
  if (shift) await page.keyboard.down('Shift');
  await page.mouse.click(s.x + fx * s.w, s.y + fy * s.h);
  if (shift) await page.keyboard.up('Shift');
}

/** The rooms as the browser holds them (the backend PUT is debounced; this is what the sheet shows). */
const roomsInBrowser = (page) => page.evaluate((id) => {
  const raw = JSON.parse(localStorage.getItem('samatu_projects') || '[]');
  const p = (Array.isArray(raw) ? raw : Object.values(raw)).find((x) => x.id === id);
  return Object.fromEntries((p?.patalpos || []).map((r) => [String(r.nr), r]));
}, PROJECT);

// SVG <text> has no innerText — read textContent
const zoneLabels = (page) => page.locator('[data-room-zone-layer] text').evaluateAll((els) => els.map((e) => e.textContent));
const toast = (page, text) => page.locator('[data-sonner-toast]').filter({ hasText: text });

test.describe('room click, room tool, Undo, scale chip', () => {
  test.beforeEach(async () => { await restoreStart(); });

  test('a click on a room selects it, Shift+click adds one, empty paper clears', async ({ page }) => {
    await openProject(page);
    await bringIntoView(page, 0.56);
    const before = (await sheet(page)).y;
    await clickSheet(page, 0.5715, 0.5435);                 // inside 04 Virtuvė/valgomasis
    await expect.poll(() => zoneLabels(page)).toEqual(expect.arrayContaining(['Virtuvė/valgomasis']));
    expect((await sheet(page)).y).toBe(before);              // the drawing did not jump to the sheet's top
    await clickSheet(page, 0.80, 0.62, { shift: true });     // + 05 Svetainė
    await expect.poll(async () => (await zoneLabels(page)).filter((t) => !t.includes('m²'))).toEqual(['Virtuvė/valgomasis', 'Svetainė']);
    await clickSheet(page, 0.15, 0.70);                      // empty paper
    await expect.poll(() => zoneLabels(page)).toEqual([]);
  });

  test('R + one click inside 06 proposes the room sheet\'s outline; Enter saves it; Atšaukti puts it back', async ({ page }) => {
    await openProject(page);
    await bringIntoView(page, 0.40);
    const start = (await roomsInBrowser(page))['06'];
    await page.keyboard.press('r');
    await expect(page.locator('[data-coach="room"]')).toHaveAttribute('aria-pressed', 'true');
    await clickSheet(page, 0.77, 0.40);
    await expect(page.locator('[data-room-proposal="06"]')).toBeVisible({ timeout: 30_000 });
    // nothing saved while it is a proposal
    expect((await roomsInBrowser(page))['06'].polygon_source).toBe(start.polygon_source);
    // what the room sheet's „Parodyti patalpą" answers for the same click
    const sheetAnswer = await page.evaluate(async (id) => {
      const res = await fetch(`/api/projects/${id}/rooms/06/outline-at`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ page: 1, x_pct: 0.77, y_pct: 0.40 }),
      });
      return res.json();
    }, PROJECT);
    expect(sheetAnswer.status).toBe('ok');
    await page.keyboard.press('Enter');
    const saved = toast(page, 'Patalpos 06 kontūras išsaugotas');
    await expect(saved).toBeVisible({ timeout: 30_000 });
    // the browser's cache is written on a short debounce
    await expect.poll(async () => (await roomsInBrowser(page))['06'].polygon_source).toBe('corrected');
    const room = (await roomsInBrowser(page))['06'];
    expect(room._konturas.saltinis).toBe('parodyta');
    const a = room.polygon_pct;
    const b = sheetAnswer.room.polygon_pct;
    expect(a.length).toBe(b.length);
    const worst = Math.max(...a.map(([x, y], i) => Math.max(Math.abs(x - b[i][0]), Math.abs(y - b[i][1]))));
    expect(worst).toBeLessThanOrEqual(0.005);
    // Atšaukti: the room's outline as it was before
    await saved.getByRole('button', { name: 'Atšaukti' }).click();
    await expect(toast(page, 'Atšaukta: patalpos 06 kontūras grąžintas')).toBeVisible({ timeout: 30_000 });
    await expect.poll(async () => (await roomsInBrowser(page))['06'].polygon_source).toBe(start.polygon_source);
    expect((await roomsInBrowser(page))['06'].polygon_pct).toEqual(start.polygon_pct);
  });

  for (const [label, escBefore, escAfter] of [['Esc, an area draft and Esc ×4', 1, 4], ['an area draft and Esc ×4 (the room still selected)', 0, 4], ['an area draft and Esc ×5', 0, 5]]) test(`after a room, ${label}, R + one click inside 06 still proposes its outline (W1-B stall)`, async ({ page }) => {
    const net = [];
    page.on('request', (r) => { if (r.url().includes('/outline-at')) net.push(`REQ ${r.url().replace(/^.*\/rooms/, '/rooms')}`); });
    page.on('response', (r) => { if (r.url().includes('/outline-at')) net.push(`RES ${r.status()} ${r.url().replace(/^.*\/rooms/, '/rooms')}`); });
    page.on('requestfailed', (r) => { if (r.url().includes('/outline-at')) net.push(`FAIL ${r.failure()?.errorText}`); });
    await openProject(page);
    await focusRoom(page, '04');                              // select a room
    for (let i = 0; i < escBefore; i += 1) await page.keyboard.press('Escape');
    await page.keyboard.press('3');                            // an area draft of three points
    for (const p of await sheetPoints(page, 1, DRAFT_04)) await clickAt(page, p);
    for (let i = 0; i < escAfter; i += 1) await page.keyboard.press('Escape');   // 3 points back, the tool off (, the room)
    await page.keyboard.press('r');
    await expect(page.locator('[data-tool="room"]')).toHaveAttribute('aria-pressed', 'true');
    const [inside06] = await sheetPoints(page, 1, [ROOM_06_INSIDE]);
    await clickAt(page, inside06);
    // the network log is read when the wait ends (a message string would be built before the wait starts)
    await expect(page.locator('[data-room-proposal="06"]')).toBeVisible({ timeout: 30_000 })
      .catch((e) => { throw new Error(`${e.message}\nnetwork: ${net.join(' | ')}`); });
    await expect(page.getByTestId('mode-pill')).not.toContainText('Skaitomas kontūras');
    expect(net.filter((l) => l.startsWith('REQ')), 'one request for the one click').toHaveLength(1);
  });

  test('an outline read still on its way when he leaves the tool is dropped: R again shows no old proposal and saves nothing', async ({ page }) => {
    let answered = 0;
    // the server takes its time, so Esc lands while the outline is still being read
    await page.route(/\/outline-at$/, async (route) => { await new Promise((r) => setTimeout(r, 2500)); await route.continue(); });
    page.on('response', (r) => { if (r.url().includes('/outline-at')) answered += 1; });
    await openProject(page);
    const start = (await roomsInBrowser(page))['06'];
    await page.keyboard.press('r');
    const [inside06] = await sheetPoints(page, 1, [ROOM_06_INSIDE]);
    await clickAt(page, inside06);
    await expect(page.getByTestId('mode-pill')).toContainText('Skaitomas kontūras');
    await page.keyboard.press('Escape');                       // he leaves the tool while it reads
    await expect(page.locator('[data-tool="room"]')).toHaveAttribute('aria-pressed', 'false');
    await expect.poll(() => answered, { timeout: 30_000 }).toBe(1);
    await page.waitForTimeout(500);
    await page.keyboard.press('r');                            // back in the tool: nothing proposed
    await expect(page.locator('[data-tool="room"]')).toHaveAttribute('aria-pressed', 'true');
    await page.waitForTimeout(500);
    await expect(page.locator('[data-room-proposal]')).toHaveCount(0);
    await expect(page.getByTestId('mode-pill')).not.toContainText('Siūlomas kontūras');
    expect((await roomsInBrowser(page))['06'].polygon_pct).toEqual(start.polygon_pct);
  });

  test('R inside 04, which no wall separates from its neighbours, says so and saves nothing', async ({ page }) => {
    await openProject(page);
    await bringIntoView(page, 0.6);
    await page.keyboard.press('r');
    await clickSheet(page, 0.55, 0.60);
    await expect(page.getByText('sienos neatskiria')).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-room-proposal]')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await expect(page.locator('[data-coach="room"]')).toHaveAttribute('aria-pressed', 'false');
  });

  test('Sujungti 04 + 05, then Atšaukti: 04 back to 26,31 m², 05 its own room, journal rows „atsaukta"', async ({ page }) => {
    await openProject(page);
    await bringIntoView(page, 0.56);
    await clickSheet(page, 0.5715, 0.5435);
    await page.locator('[data-testid="outline-tool-merge"]').click();
    const s = await sheet(page);
    await page.mouse.move(s.x + 0.80 * s.w, s.y + 0.62 * s.h);
    await clickSheet(page, 0.80, 0.62);
    await page.keyboard.press('Enter');
    const merged = toast(page, 'prijungta prie 04');
    await expect(merged).toBeVisible({ timeout: 30_000 });
    await expect.poll(async () => (await roomsInBrowser(page))['05']._sujungta_i ?? null).toBe('04');
    expect((await roomsInBrowser(page))['04'].plotas_m2).toBe(61.81);
    await merged.getByRole('button', { name: 'Atšaukti' }).click();
    await expect(toast(page, 'Atšaukta: patalpos 04 ir 05 vėl atskiros')).toBeVisible({ timeout: 30_000 });
    await expect.poll(async () => (await roomsInBrowser(page))['04'].plotas_m2).toBe(26.31);
    const rooms = await roomsInBrowser(page);
    expect(rooms['05']._sujungta_i ?? null).toBe(null);
    expect(rooms['05'].polygon_pct?.length).toBeGreaterThan(2);
    const journal = await api(`/api/projects/${PROJECT}/corrections`);
    const rows = (journal.corrections || journal.items || journal).filter((c) => c.source === 'atsaukta');
    expect(rows.map((c) => c.room_nr)).toEqual(expect.arrayContaining(['04', '05']));
  });

  test('Atimti a column from 06, then Atšaukti: the hole is gone', async ({ page }) => {
    await openProject(page);
    await bringIntoView(page, 0.40);
    await clickSheet(page, 0.77, 0.40);                      // select 06
    await page.locator('[data-testid="outline-tool-subtract"]').click();
    const s = await sheet(page);
    await page.mouse.move(s.x + 0.72 * s.w, s.y + 0.37 * s.h);
    await page.mouse.down();
    await page.mouse.move(s.x + 0.73 * s.w, s.y + 0.38 * s.h, { steps: 3 });
    await page.mouse.move(s.x + 0.74 * s.w, s.y + 0.39 * s.h, { steps: 3 });
    await page.mouse.up();
    await page.locator('[data-testid="outline-tool-save"]').click();
    const saved = toast(page, 'išpjova');
    await expect(saved).toBeVisible({ timeout: 30_000 });
    await expect.poll(async () => (await roomsInBrowser(page))['06'].polygon_holes_pct?.length ?? 0).toBe(1);
    await saved.getByRole('button', { name: 'Atšaukti' }).click();
    await expect(toast(page, 'Atšaukta: patalpos 06 kontūras grąžintas')).toBeVisible({ timeout: 30_000 });
    await expect.poll(async () => (await roomsInBrowser(page))['06'].polygon_holes_pct ?? null).toBe(null);
  });

  test('the scale chip: „1:115 · spėjamas", one click confirms it, „Kalibruoti" arms the calibrate tool', async ({ page }) => {
    await openProject(page);
    const chip = page.locator('[data-testid="scale-chip"]');
    await expect(chip).toHaveAttribute('data-scale-state', 'spejamas');
    await expect(chip).toContainText('1:115');
    // the card: where the scale comes from, this sheet or all eight; Esc closes it before anything else
    await chip.click();
    await expect(page.locator('[data-testid="scale-chip-confirm-all"]')).toContainText('visiems 8 lapams');
    await expect(page.locator('[data-testid="scale-chip-confirm"]')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('[data-testid="scale-chip-card"]')).toHaveCount(0);
    // ONE click on the chip's own „Patvirtinti"
    await page.locator('[data-testid="scale-chip-confirm-inline"]').click();
    await expect(chip).toHaveAttribute('data-scale-state', 'patvirtintas');
    await expect(page.locator('[data-testid="scale-chip-confirm-inline"]')).toHaveCount(0);
    await chip.click();
    await page.locator('[data-testid="scale-chip-calibrate"]').click();
    await expect(page.locator('[data-coach="calibrate"]')).toHaveAttribute('aria-pressed', 'true');
    await page.keyboard.press('Escape');
  });
});
