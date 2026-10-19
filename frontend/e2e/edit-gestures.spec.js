/**
 * Editing gestures (Pathon v3, wave 5, track W5-A) on the demo project (demo-objektas_h).
 *
 *  A1  double-click a room → its outline editor (same as E); double-click a measurement → its points;
 *  A2  the corner / edge pop-up: „Iškirpti angą" adds a door to the room; on a perimeter it cuts the doorway gap;
 *  A3  drag an edge (both corners move), box-select corners, Delete removes them, arrows nudge;
 *  A4  „Atimti" + one click on a column → the column proposed as the hole → Enter;
 *  A5  „Žymėti" box selection (left→right whole, right→left touched) for marks and rooms; „Pažymėti panašias";
 *  A6  Ctrl held jumps to the snap target; midpoints; the status line names the snap;
 *  A7  the count-type picker at the pointer; a quick second click on a fresh mark is ignored;
 *  A8  right-click a mark → „Rasti panašius" with the template box drawn;
 *  A9  click an opening on the walls layer → width + kind → saved, „Atšaukti";
 *  A11 rectangle, arc, typed length, copy / paste / duplicate;
 *  A12 click a wall face → its length as a distance.
 * Click counts against design §2 T1 are written into the report through note().
 *
 * WRITES to the project — part of `npm run test:e2e`: every test restores the guide's start state first.
 * Other ports: E2E_BASE_URL / E2E_API_URL (W5-A: 5214 / 8134); backend with auth off.
 */
import { expect } from './pw.js';
import { PROJECT } from './state.js';
import { it, note, restoreStart, shot } from './helpers.js';

const test = it;

async function openProject(page) {
  await page.addInitScript(() => {
    try {
      localStorage.setItem('samatu_viewer_onboarded', '1');
      localStorage.setItem('pathon_cookie_consent', JSON.stringify({ categories: { necessary: true, analytics: false, marketing: false }, timestamp: Date.now() }));
    } catch { /* private mode */ }
  });
  await page.goto(`/project/${PROJECT}`);
  await expect(page.locator('[data-takeoff-viewer] [data-page-number="1"]')).toBeAttached({ timeout: 30_000 });
  await expect(page.getByText('Kraunamas dokumentas', { exact: false })).toHaveCount(0, { timeout: 60_000 });
  await page.waitForTimeout(1500);
}

const sheet = (page) => page.evaluate(() => {
  const b = document.querySelector('[data-takeoff-viewer] [data-page-number="1"]').getBoundingClientRect();
  return { x: b.x, y: b.y, w: b.width, h: b.height };
});

/** Scroll the drawing so the sheet fraction (fx, fy) sits mid-canvas. */
async function bringIntoView(page, fx, fy) {
  await page.evaluate(([x, y]) => {
    const pg = document.querySelector('[data-takeoff-viewer] [data-page-number="1"]');
    let s = pg.parentElement;
    while (s && !(s.scrollHeight > s.clientHeight + 10 && /(auto|scroll)/.test(getComputedStyle(s).overflowY))) s = s.parentElement;
    const r = pg.getBoundingClientRect();
    const sr = s.getBoundingClientRect();
    s.scrollBy({ left: r.left + x * r.width - (sr.left + sr.width / 2), top: r.top + y * r.height - (sr.top + sr.height / 2), behavior: 'instant' });
  }, [fx, fy]);
  await page.waitForTimeout(500);
}

const at = async (page, fx, fy) => { const s = await sheet(page); return { x: s.x + fx * s.w, y: s.y + fy * s.h }; };

/** Counted pointer actions (clicks, double-clicks as 2, drags) and keys — for the T1 click counts. */
function counter() {
  const c = { clicks: 0, drags: 0, keys: 0 };
  return {
    c,
    async click(page, p, opts = {}) { c.clicks += 1; await page.mouse.move(p.x, p.y, { steps: 4 }); await page.mouse.click(p.x, p.y, opts); await page.waitForTimeout(120); },
    async dbl(page, p) { c.clicks += 2; await page.mouse.move(p.x, p.y, { steps: 4 }); await page.mouse.dblclick(p.x, p.y); await page.waitForTimeout(200); },
    async drag(page, a, b) { c.drags += 1; await page.mouse.move(a.x, a.y, { steps: 3 }); await page.mouse.down(); await page.mouse.move(b.x, b.y, { steps: 12 }); await page.mouse.up(); await page.waitForTimeout(150); },
    async key(page, k) { c.keys += 1; await page.keyboard.press(k); await page.waitForTimeout(120); },
    text() { return `${c.clicks} spustelėjimai + ${c.drags} tempimai + ${c.keys} klavišai = ${c.clicks + c.drags + c.keys}`; },
  };
}

/** The rooms / measurements as the browser holds them (the backend PUT is debounced). */
const stored = (page) => page.evaluate((id) => {
  const raw = JSON.parse(localStorage.getItem('samatu_projects') || '[]');
  const p = (Array.isArray(raw) ? raw : Object.values(raw)).find((x) => x.id === id);
  return { rooms: Object.fromEntries((p?.patalpos || []).map((r) => [String(r.nr), r])), measurements: p?.measurements || [], countTypes: p?.countTypes || [] };
}, PROJECT);

const toast = (page, text) => page.locator('[data-sonner-toast]').filter({ hasText: text });
const vertexBox = (page, i) => page.locator(`[data-outline-vertex="${i}"] circle`).first().boundingBox();
const centre = (b) => ({ x: b.x + b.width / 2, y: b.y + b.height / 2 });

// Room 06 Vaiko kambarys (six corners, a vector outline) and a spot inside it.
const ROOM_06 = [0.77, 0.40];

test.describe('W5-A editing gestures', () => {
  test.beforeEach(async () => { await restoreStart(); });

  test('A1 + A3: double-click 06 edits its outline; one corner dragged, Enter saves, Atšaukti — T1 „fix a vertex"', async ({ page }) => {
    await openProject(page);
    await bringIntoView(page, ...ROOM_06);
    const start = (await stored(page)).rooms['06'];
    const k = counter();
    await k.dbl(page, await at(page, ...ROOM_06));
    await expect(page.locator('[data-outline-edit-layer]')).toBeVisible();
    await expect(page.getByTestId('mode-pill')).toContainText('Kontūras · patalpa 06');
    await shot(page, 'w5a-a1-room-dblclick');
    const v = centre(await vertexBox(page, 4));
    await k.drag(page, v, { x: v.x + 14, y: v.y });
    await k.key(page, 'Enter');
    const saved = toast(page, 'Patalpos 06 kontūras išsaugotas');
    await expect(saved).toBeVisible({ timeout: 30_000 });
    note(`T1 pataisyti viršūnę (n = 1): ${k.text()} (tikslas 2+n)`);
    await expect.poll(async () => JSON.stringify((await stored(page)).rooms['06'].polygon_pct)).not.toBe(JSON.stringify(start.polygon_pct));
    await saved.getByRole('button', { name: 'Atšaukti' }).click();
    await expect(toast(page, 'Atšaukta: patalpos 06 kontūras grąžintas')).toBeVisible({ timeout: 30_000 });
  });

  test('A3: an edge drag moves both its corners; a box picks two corners, Delete removes them; an arrow nudges', async ({ page }) => {
    await openProject(page);
    await bringIntoView(page, ...ROOM_06);
    await page.mouse.dblclick(...Object.values(await at(page, ...ROOM_06)));
    await expect(page.locator('[data-outline-edit-layer]')).toBeVisible();
    const before = await Promise.all([0, 1, 2, 3, 4, 5].map((i) => vertexBox(page, i).then(centre)));
    // edge 1 runs from corner 1 to corner 2 (the bottom wall): grab it a quarter of the way along, drag down
    const grab = { x: before[1].x + (before[2].x - before[1].x) * 0.25, y: before[1].y + (before[2].y - before[1].y) * 0.25 };
    await page.mouse.move(grab.x, grab.y, { steps: 3 });
    await page.mouse.down();
    await page.mouse.move(grab.x, grab.y + 20, { steps: 10 });
    await page.mouse.up();
    const after = await Promise.all([1, 2].map((i) => vertexBox(page, i).then(centre)));
    expect(after[0].y - before[1].y).toBeGreaterThan(8);
    expect(Math.abs((after[0].y - before[1].y) - (after[1].y - before[2].y))).toBeLessThan(1.5);
    await shot(page, 'w5a-a3-edge-drag');
    // Z undoes the drag; then a box round corners 4 and 5 (the top-left notch), Delete
    await page.keyboard.press('z');
    const b4 = before[4]; const b5 = before[5];
    const lo = { x: Math.min(b4.x, b5.x) - 12, y: Math.min(b4.y, b5.y) - 12 };
    const hi = { x: Math.max(b4.x, b5.x) + 12, y: Math.max(b4.y, b5.y) + 12 };
    // start the box on empty paper outside the room, above the notch
    await page.mouse.move(lo.x, lo.y - 30, { steps: 2 });
    await page.mouse.down();
    await page.mouse.move(hi.x, hi.y, { steps: 10 });
    await page.mouse.up();
    await expect(page.locator('[data-outline-vertex][data-selected="true"]')).toHaveCount(2);
    await page.keyboard.press('Delete');
    await expect(page.locator('[data-outline-vertex]')).toHaveCount(4);
    // one corner clicked: selected, its pop-up open; the arrow key moves it, Esc closes the pop-up only
    await page.mouse.click(...Object.values(centre(await vertexBox(page, 0))));
    await expect(page.getByTestId('vertex-popover')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('vertex-popover')).toHaveCount(0);
    await expect(page.locator('[data-outline-edit-layer]')).toBeVisible();
    const c0 = centre(await vertexBox(page, 0));
    await page.keyboard.press('Shift+ArrowRight');
    const c1 = centre(await vertexBox(page, 0));
    expect(Math.round(c1.x - c0.x)).toBe(10);
    await page.keyboard.press('Escape');                      // leaves without saving
    await expect(page.locator('[data-outline-edit-layer]')).toHaveCount(0);
  });

  test('A1 + A2: a perimeter double-clicked edits its points; a corner\'s „Iškirpti angą" cuts the doorway out', async ({ page }) => {
    await openProject(page);
    await bringIntoView(page, 0.6, 0.5);
    const startCount = (await stored(page)).measurements.length;
    await page.keyboard.press('4');
    for (const [fx, fy] of [[0.50, 0.48], [0.62, 0.48], [0.62, 0.56]]) await page.mouse.click(...Object.values(await at(page, fx, fy)));
    await page.keyboard.press('Enter');
    await expect(toast(page, 'Perimetras')).toBeVisible();
    await page.keyboard.press('Escape');                      // back to rest
    await page.waitForTimeout(300);
    await page.mouse.dblclick(...Object.values(await at(page, 0.56, 0.48)));
    await expect(page.locator('[data-outline-edit-layer][data-closed="false"]')).toBeVisible();
    await expect(page.getByTestId('mode-pill')).toContainText('Perimetras · taškai');
    await page.mouse.click(...Object.values(centre(await vertexBox(page, 1))));
    await expect(page.getByTestId('vertex-popover')).toBeVisible();
    await shot(page, 'w5a-a2-vertex-popover');
    await page.getByTestId('vertex-cut').click();
    await expect(toast(page, 'liko dvi atkarpos')).toBeVisible();
    await expect.poll(async () => (await stored(page)).measurements.length).toBe(startCount + 2);
  });

  test('A2: on a room outline „Iškirpti angą" adds a door to the room, Atšaukti takes it away', async ({ page }) => {
    await openProject(page);
    await bringIntoView(page, ...ROOM_06);
    const before = (await stored(page)).rooms['06'].elementai || [];
    await page.mouse.dblclick(...Object.values(await at(page, ...ROOM_06)));
    await expect(page.locator('[data-outline-edit-layer]')).toBeVisible();
    const a = centre(await vertexBox(page, 1)); const b = centre(await vertexBox(page, 2));
    await page.mouse.click(a.x + (b.x - a.x) * 0.3, a.y + (b.y - a.y) * 0.3, { button: 'right' });
    await expect(page.getByTestId('vertex-popover')).toBeVisible();
    await page.getByTestId('vertex-cut').click();
    const added = toast(page, 'Patalpai 06 pridėta');
    await expect(added).toBeVisible({ timeout: 20_000 });
    await expect.poll(async () => JSON.stringify((await stored(page)).rooms['06'].elementai)).not.toBe(JSON.stringify(before));
    expect((await stored(page)).rooms['06']._angos_user_at).toBeTruthy();
    await added.getByRole('button', { name: 'Atšaukti' }).click();
    await expect(toast(page, 'Atšaukta: patalpos 06 angos grąžintos')).toBeVisible();
    await expect.poll(async () => JSON.stringify((await stored(page)).rooms['06'].elementai || [])).toBe(JSON.stringify(before));
  });

  test('A5: „Žymėti" box — left→right takes whole rooms, right→left touched ones; „Pažymėti panašias"', async ({ page }) => {
    await openProject(page);
    const { rooms } = await stored(page);
    const bb = (nr) => {
      const r = rooms[nr].polygon_pct;
      return { x0: Math.min(...r.map((p) => p[0])), y0: Math.min(...r.map((p) => p[1])), x1: Math.max(...r.map((p) => p[0])), y1: Math.max(...r.map((p) => p[1])) };
    };
    const a = bb('07'); const b = bb('08');
    const box = { x0: Math.min(a.x0, b.x0) - 0.004, y0: Math.min(a.y0, b.y0) - 0.004, x1: Math.max(a.x1, b.x1) + 0.004, y1: Math.max(a.y1, b.y1) + 0.004 };
    await bringIntoView(page, (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2);
    await page.keyboard.press('1');
    const k = counter();
    await k.drag(page, await at(page, box.x0, box.y0), await at(page, box.x1, box.y1));
    const bar = page.getByTestId('selection-bar');
    await expect(bar).toBeVisible();
    await expect(bar).toContainText('07');
    await expect(bar).toContainText('08');
    note(`dvi patalpos rėmeliu: ${k.text()}`);
    await shot(page, 'w5a-a5-box-window');
    // right→left, a box that only touches 07's middle: 07 alone (08 lies outside it)
    const mx = (a.x0 + a.x1) / 2; const my = (a.y0 + a.y1) / 2;
    await k.drag(page, await at(page, mx + 0.004, my - 0.004), await at(page, mx - 0.004, my + 0.004));
    await expect(bar).toContainText('07');
    await expect(bar).not.toContainText('08');
    // 06 Vaiko kambarys + „Pažymėti panašias" → the other bedroom joins
    await page.keyboard.press('Escape');
    await page.keyboard.press('Escape');
    await bringIntoView(page, ...ROOM_06);
    await page.mouse.click(...Object.values(await at(page, ...ROOM_06)));
    await page.getByTestId('selection-similar').click();
    await page.getByTestId('selection-similar-paskirtis').click();
    await expect(bar).toContainText('06 + 09');
  });

  test('A6: Ctrl held jumps to the nearest snap; the status line names what the click will land on', async ({ page }) => {
    await openProject(page);
    await bringIntoView(page, ...ROOM_06);
    const seen = new Set();
    page.on('response', (r) => { const m = /\/pages\/(\d+)\/geometry/.exec(r.url()); if (m && r.ok()) seen.add(Number(m[1])); });
    await page.keyboard.press('2');
    await expect.poll(() => seen.has(1), { timeout: 30_000 }).toBe(true);
    await page.waitForTimeout(500);
    // a spot in open floor, ~20 px from the nearest wall line at this zoom: no snap without Ctrl
    const s = await sheet(page);
    const free = { x: s.x + 0.705 * s.w, y: s.y + 0.405 * s.h };
    await page.mouse.move(free.x, free.y, { steps: 3 });
    await page.mouse.move(free.x + 1, free.y + 1);
    await expect(page.locator('[data-snap^="drawing"]')).toHaveCount(0);
    await page.keyboard.down('Control');
    await page.mouse.move(free.x + 2, free.y + 2);
    await expect(page.locator('[data-snap]')).toHaveCount(1);
    await expect(page.getByText(/^Prilimpa: /)).toBeVisible();
    await shot(page, 'w5a-a6-ctrl-jump');
    await page.keyboard.up('Control');
    await page.keyboard.press('Escape');
  });

  test('A4: „Atimti" + one click on a drawn figure proposes it as the hole, Enter saves it — T1 „subtract a column"', async ({ page }) => {
    await openProject(page);
    await bringIntoView(page, ...ROOM_06);
    await page.mouse.click(...Object.values(await at(page, ...ROOM_06)));      // the room selected first
    await expect(page.getByTestId('outline-tool-subtract')).toBeVisible();
    const k = counter();
    await k.key(page, 'x');
    await expect(page.locator('[data-outline-tool-layer="subtract"]')).toBeVisible();
    await k.click(page, await at(page, 0.785, 0.358));
    await expect(page.locator('[data-proposed-hole]')).toBeVisible({ timeout: 20_000 });
    await expect(page.locator('[data-outline-tool-chip]').filter({ hasText: 'Enter: atimti' })).toBeVisible();
    // nothing saved while it is a proposal
    expect((await stored(page)).rooms['06'].polygon_holes_pct ?? null).toBeNull();
    await shot(page, 'w5a-a4-proposed-hole');
    await k.key(page, 'Enter');
    const saved = toast(page, 'kontūras išsaugotas su 1 išpjova');
    await expect(saved).toBeVisible({ timeout: 30_000 });
    note(`T1 atimti koloną (patalpa jau pažymėta): ${k.text()} (tikslas 3; su patalpos spustelėjimu +1)`);
    await expect.poll(async () => ((await stored(page)).rooms['06'].polygon_holes_pct || []).length).toBe(1);
    await saved.getByRole('button', { name: 'Atšaukti' }).click();
    await expect(toast(page, 'Atšaukta: patalpos 06 kontūras grąžintas')).toBeVisible({ timeout: 30_000 });
  });
});
