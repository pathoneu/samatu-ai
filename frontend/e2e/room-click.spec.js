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
 * WRITES to the project (outline saves, merges, a confirmed scale): run it against a COPY of the database (a
 * worktree's backend/data). It starts from the stored version that is the founder guide's start state (04 not
 * merged, no scale confirmed — the same rule W0-A's global setup uses) and restores that version again at the
 * end. Relative URLs: the suite's `baseURL` (e.g. http://localhost:5206), backend with auth off.
 */
import { test, expect } from '@playwright/test';

const PROJECT = process.env.PATHON_E2E_PROJECT || 'demo-objektas_h';

const isStart = (p) => {
  const rooms = Object.fromEntries((p.patalpos || []).map((r) => [String(r.nr), r]));
  const confirmed = Object.values(p.pageScalesDurable || {}).filter((s) => s && s.confirmed).length;
  return rooms['04']?.plotas_m2 === 26.31 && !rooms['05']?._sujungta_i && confirmed === 0;
};

/** Restore the newest stored version that is the guide's start state; → its id. */
async function restoreStart(request) {
  const { versions } = await (await request.get(`/api/projects/${PROJECT}/versions`)).json();
  for (const v of versions) {
    const full = await (await request.get(`/api/projects/${PROJECT}/versions/${v.id}`)).json();
    if (isStart(full.data || {})) {
      const res = await request.post(`/api/projects/${PROJECT}/versions/${v.id}/restore`);
      expect(res.ok()).toBeTruthy();
      return v.id;
    }
  }
  throw new Error(`no stored version of ${PROJECT} is the start state (04 = 26,31 m², 05 not merged, no confirmed scale)`);
}

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

test.describe.configure({ mode: 'serial' });

test.describe('room click, room tool, Undo, scale chip', () => {
  test.beforeAll(async ({ request }) => { await restoreStart(request); });
  test.afterAll(async ({ request }) => { await restoreStart(request); });

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

  test('Sujungti 04 + 05, then Atšaukti: 04 back to 26,31 m², 05 its own room, journal rows „atsaukta"', async ({ page, request }) => {
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
    const journal = await (await request.get(`/api/projects/${PROJECT}/corrections`)).json();
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
