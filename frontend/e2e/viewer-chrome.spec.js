/**
 * Viewer chrome and zones in the viewer (Pathon v3, wave 5, track W5-B) on the demo project (demo-objektas_h).
 *
 *  - B1 the sheet header: badge, name, „← 1 iš 8 →"; the arrows, PageDown / PageUp step sheets;
 *  - B2 zones: hovering sheet 3's legend outlines it and names it („Legenda · …"), leaving clears it; „Rodyti
 *    sritis" in „Rodinys" draws every zone, the plan included;
 *  - B4 „Rodinys": greyscale / opacity reach the drawing only, the card closes on Esc and the room stays selected;
 *  - B5 the zoom column: +, −, fit, area zoom, minimap; nothing overlaps the mode pill at 1280 × 720;
 *  - B6 the one confirm box: 300 px with its consequence sentence; Esc closes the box only (the drawer under it
 *    stays open); a measurement deleted from the selection bar comes back with the toast's „Atšaukti";
 *  - B7 focusing a room from the list frames the ROOM (zoom up, its marker near the window's centre);
 *  - B8 the scale chip: a typed 1:50 becomes his scale, „Atšaukti" puts 1:115 back;
 *  - B9 „Neskaityti šio lapo" is stored on the project and undone from the toast;
 *  - B10 Matavimai: a group, a measurement dragged into it, the filters.
 *
 * WRITES to the project (a scale, a skip flag, a group, measurements) — part of `npm run test:e2e`: every test starts
 * from the guide's start state and the suite's teardown puts the pristine database back. W5-B ports: 5215 / 8135.
 */
import { expect } from './pw.js';
import { getProject } from './state.js';
import { clickAt, it, note, openProject, restoreStart, roomRow, sheetPoints, shot, toast } from './helpers.js';

const test = it;

const pager = (page) => page.getByTestId('sheet-pager');
const zoomPct = async (page) => Number((await page.getByTestId('zoom-level').innerText()).replace(/\D/g, ''));
const box = async (loc) => loc.boundingBox();
const overlaps = (a, b) => !!a && !!b && a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

async function pageBox(page, nr) {
  return page.evaluate((n) => {
    const r = document.querySelector(`[data-takeoff-viewer] [data-page-number="${n}"]`).getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  }, nr);
}

test.describe('viewer chrome (W5-B)', () => {
  test.beforeEach(async () => { await restoreStart(); });

  test('B1 the header names the sheet; arrows and PageDown / PageUp step sheets', async ({ page }) => {
    await openProject(page);
    await expect(pager(page)).toHaveText('1 iš 8');
    await expect(page.getByTestId('sheet-badge')).toHaveText('1');
    await expect(page.getByTestId('sheet-name')).toContainText('PLANAS');
    await expect(page.getByTestId('sheet-prev')).toBeDisabled();
    await page.getByTestId('sheet-next').click();
    await expect(pager(page)).toHaveText('2 iš 8');
    await page.mouse.move(700, 450);
    await page.keyboard.press('PageDown');
    await expect(pager(page)).toHaveText('3 iš 8');
    await expect(page.getByTestId('sheet-name')).toContainText('APŠVIETIMO');
    await page.keyboard.press('PageUp');
    await expect(pager(page)).toHaveText('2 iš 8');
    note('sheet header: 1 → (→) 2 → (PgDn) 3 → (PgUp) 2');
  });

  test('B2 hovering sheet 3\'s legend outlines and names it; „Rodyti sritis" draws every zone', async ({ page }) => {
    await openProject(page);
    await page.mouse.move(700, 450);
    await page.keyboard.press('PageDown');
    await expect(pager(page)).toHaveText('2 iš 8');
    await page.waitForTimeout(800);
    await page.keyboard.press('PageDown');
    await expect(pager(page)).toHaveText('3 iš 8');
    await page.waitForTimeout(800);
    await page.getByTestId('zoom-fit-page').click();
    await page.waitForTimeout(1200);
    await page.locator('[data-takeoff-viewer] [data-page-number="3"]').scrollIntoViewIfNeeded();
    await page.waitForTimeout(600);
    const b = await pageBox(page, 3);
    // the luminaire legend: (0,06–0,22) × (0,50–0,68) of the sheet
    await page.mouse.move(b.x + 0.14 * b.w, b.y + 0.59 * b.h);
    await page.mouse.move(b.x + 0.141 * b.w, b.y + 0.592 * b.h, { steps: 3 });
    const layer = page.locator('[data-sheet-zone-layer="3"]');
    await expect(layer.locator('[data-sheet-zone="legenda"]')).toHaveCount(1, { timeout: 30_000 });
    await expect(layer.locator('[data-sheet-zone="legenda"] text').first()).toContainText('Legenda');
    await expect(layer.locator('[data-sheet-zone="planas"]')).toHaveCount(0);
    await shot(page, 'w5b-zone-hover');
    // on the plan alone: nothing outlined
    await page.mouse.move(b.x + 0.5 * b.w, b.y + 0.35 * b.h, { steps: 3 });
    await expect(layer.locator('[data-sheet-zone]')).toHaveCount(0);
    await page.getByTestId('view-settings-toggle').click();
    await page.getByTestId('view-zones').click();
    await expect(layer.locator('[data-sheet-zone="planas"]')).toHaveCount(1);
    const n = await layer.locator('[data-sheet-zone]').count();
    expect(n).toBeGreaterThanOrEqual(5);
    note(`sheet 3: hover → Legenda; „Rodyti sritis" → ${n} zones`);
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('view-settings')).toHaveCount(0);
  });

  test('B4 „Rodinys" reaches the drawing only; Esc closes the card and keeps the selected room', async ({ page }) => {
    await openProject(page);
    await roomRow(page, '02').click();
    await expect(page.getByTestId('selection-bar')).toBeVisible();
    await page.getByTestId('view-settings-toggle').click();
    await page.getByTestId('view-gray').click();
    const filter = await page.evaluate(() => getComputedStyle(document.querySelector('[data-takeoff-viewer] [data-drawing-render]')).filter);
    expect(filter).toContain('grayscale');
    const markFilter = await page.evaluate(() => {
      const el = document.querySelector('[data-room-zone-layer]');
      return el ? getComputedStyle(el).filter : 'none';
    });
    expect(markFilter).toBe('none');
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('view-settings')).toHaveCount(0);
    await expect(page.getByTestId('selection-bar'), 'the card took the Esc, the room stays selected').toBeVisible();
    // the setting is remembered and can be put back with Atšaukti
    await page.getByTestId('view-settings-toggle').click();
    await page.getByTestId('view-reset').click();
    await expect(toast(page, 'Rodinys grąžintas')).toBeVisible();
  });

  test('B5 the zoom column: ±, fit, area zoom, minimap; it never covers the pill at 1280 × 720', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openProject(page);
    const z0 = await zoomPct(page);
    await page.getByTestId('zoom-in').click();
    await expect.poll(() => zoomPct(page)).toBeGreaterThan(z0);
    await page.getByTestId('zoom-out').click();
    await page.getByTestId('zoom-fit-page').click();
    const fit = await zoomPct(page);
    // area zoom: a box around a quarter of the sheet fills the window
    await page.getByTestId('zoom-area').click();
    const b = await pageBox(page, 1);
    const canvas = await box(page.getByTestId('viewer-canvas'));
    const x0 = Math.max(b.x, canvas.x) + 40;
    const y0 = Math.max(b.y, canvas.y) + 60;
    await page.mouse.move(x0, y0);
    await page.mouse.down();
    await page.mouse.move(x0 + 120, y0 + 90, { steps: 5 });
    await page.mouse.up();
    await expect.poll(() => zoomPct(page), { timeout: 10_000 }).toBeGreaterThan(fit * 2);
    note(`area zoom ${fit} % → ${await zoomPct(page)} %`);
    await page.getByTestId('zoom-minimap').click();
    await expect(page.getByTestId('minimap-frame')).toBeVisible();
    await page.getByTestId('zoom-minimap').click();
    // the pill (area tool) and the column side by side, one line each
    await page.mouse.move(600, 400);
    await page.keyboard.press('3');
    const pill = await box(page.getByTestId('mode-pill'));
    const col = await box(page.locator('[data-zoom-cluster]'));
    expect(overlaps(pill, col)).toBe(false);
    expect(pill.height).toBeLessThan(56);
    note(`1280×720: pill ${Math.round(pill.width)}×${Math.round(pill.height)} px, zoom column ${Math.round(col.width)} px wide`);
    await shot(page, 'w5b-1280-pill-zoom');
    await page.keyboard.press('Escape');
  });

  test('B6 the confirm box is 300 px with its consequence; Esc closes only the box; a deleted measurement comes back', async ({ page }) => {
    await openProject(page);
    await page.getByRole('button', { name: 'Versijos', exact: true }).click();
    const drawer = page.getByRole('dialog', { name: 'Projekto versijos' });
    const older = drawer.getByRole('listitem').nth(1);
    await older.getByRole('button', { name: 'Grąžinti' }).click();
    const confirm = page.getByTestId('confirm-box');
    await expect(confirm).toBeVisible();
    expect(Math.round((await box(confirm)).width)).toBe(300);
    await expect(page.getByTestId('confirm-consequence')).toContainText('Prieš grąžinant');
    await page.keyboard.press('Escape');
    await expect(confirm).toHaveCount(0);
    await expect(drawer, 'Esc closed the box only').toBeVisible();
    await shot(page, 'w5b-confirm');
    await drawer.getByRole('button', { name: 'Uždaryti versijas' }).click();
    await expect(drawer).toHaveCount(0);
    // the start state has no measurement: draw a distance in room 04 first (W1-B's points)
    {
      await page.mouse.move(700, 450);
      await page.keyboard.press('2');
      for (const pt of await sheetPoints(page, 1, [[0.50, 0.52], [0.58, 0.52]])) await clickAt(page, pt);
      await page.keyboard.press('Escape');
      await expect.poll(async () => ((await getProject()).measurements || []).filter((x) => x.kind === 'distance').length, { timeout: 15_000 }).toBe(1);
    }
    // a measurement: select it, delete from the selection bar, Atšaukti
    const before = ((await getProject()).measurements || []).length;
    await page.mouse.move(700, 450);
    await page.keyboard.press('1');
    // the start state's distance on sheet 1, clicked in its middle with „Žymėti" (sheet 1: A4 portrait, no /Rotate)
    const [midPt] = await sheetPoints(page, 1, [[0.54, 0.52]]);
    await clickAt(page, midPt);
    const del = page.getByTestId('selection-bar').getByRole('button', { name: /Ištrinti/ });
    await expect(del).toBeVisible();
    await del.click();
    await expect.poll(async () => (await getProject()).measurements.length, { timeout: 15_000 }).toBe(before - 1);
    await toast(page, 'Matavimas ištrintas').getByRole('button', { name: 'Atšaukti' }).click();
    await expect.poll(async () => (await getProject()).measurements.length, { timeout: 15_000 }).toBe(before);
    note('confirm box 300 px; Esc closed the box, drawer stayed; measurement delete → Atšaukti → back');
  });

  test('B7 a room focused from the list is framed, not its page', async ({ page }) => {
    await openProject(page);
    const z0 = await zoomPct(page);
    await roomRow(page, '06').click();
    await expect.poll(() => zoomPct(page), { timeout: 10_000 }).toBeGreaterThan(z0 * 1.5);
    const off = await page.evaluate(() => {
      const ring = document.querySelector('[data-room-ring="06"], [data-room-zone="06"]');
      const c = document.querySelector('[data-testid="viewer-canvas"]').getBoundingClientRect();
      const b = ring.getBoundingClientRect();
      return { dx: Math.abs(b.x + b.width / 2 - (c.x + c.width / 2)), dy: Math.abs(b.y + b.height / 2 - (c.y + c.height / 2)), w: c.width, h: c.height };
    });
    expect(off.dx).toBeLessThan(off.w * 0.2);
    expect(off.dy).toBeLessThan(off.h * 0.2);
    note(`focus 06: zoom ${z0} % → ${await zoomPct(page)} %, centre off by ${Math.round(off.dx)} / ${Math.round(off.dy)} px`);
  });

  test('B8 a typed 1:50 becomes his scale and Atšaukti puts 1:115 back', async ({ page }) => {
    await openProject(page);
    await page.getByTestId('scale-chip').click();
    await expect(page.getByTestId('scale-chip-entry')).toContainText('A4');
    await page.getByTestId('scale-chip-ratio').fill('1:50');
    await page.getByTestId('scale-chip-ratio-apply').click();
    await expect(page.getByTestId('scale-chip')).toContainText('1:50');
    await toast(page, 'mastelis 1:50').getByRole('button', { name: 'Atšaukti' }).click();
    await expect(page.getByTestId('scale-chip')).toContainText('1:115');
  });

  test('B9 „Neskaityti šio lapo" is stored on the project and undone from the toast', async ({ page }) => {
    await page.addInitScript(() => { try { localStorage.setItem('samatu_viewer_sheet_rail', 'full'); } catch { /* */ } });
    await openProject(page);
    await page.getByTestId('sheet-skip').first().click();
    await expect.poll(async () => (await getProject()).neskaitomi_lapai || [], { timeout: 15_000 }).toEqual([1]);
    await expect(page.getByTestId('sheet-skipped-tag')).toHaveCount(1);
    await toast(page, 'nebus skaitomas').getByRole('button', { name: 'Atšaukti' }).click();
    await expect.poll(async () => (await getProject()).neskaitomi_lapai || [], { timeout: 15_000 }).toEqual([]);
  });

  test('B10 Matavimai: a named group, a measurement dragged into it, the filters', async ({ page }) => {
    await openProject(page);
    // the start state has no measurement: two distances and a count mark
    await page.mouse.move(700, 450);
    await page.keyboard.press('2');
    for (const pair of [[[0.50, 0.52], [0.58, 0.52]], [[0.50, 0.56], [0.58, 0.56]]]) {
      for (const pt of await sheetPoints(page, 1, pair)) await clickAt(page, pt);
    }
    await page.keyboard.press('Escape');
    await expect.poll(async () => ((await getProject()).measurements || []).length, { timeout: 15_000 }).toBe(2);
    await page.getByTestId('meas-group-add').click();
    await page.getByTestId('meas-group-name-input').fill('Virtuvė');
    await page.getByTestId('meas-group-name-input').press('Enter');
    await expect(page.getByTestId('meas-group-head')).toContainText('Virtuvė');
    // the „+" in the group's head adds by click (nothing drag-only), then a drag moves another
    await page.getByTestId('meas-group-pick').click();
    await page.getByTestId('meas-group-picker').getByRole('button').first().click();
    await expect.poll(async () => Object.keys((await getProject()).measureGroups?.members || {}).length, { timeout: 15_000 }).toBe(1);
    const loose = page.locator('[data-meas-group=""] [data-measure-drag]').first();
    await expect(loose).toHaveCount(1);
    {
      // the panel scrolls under its sticky headers: bring the group's head to the middle, the row sits just below
      await page.getByTestId('meas-group-head').evaluate((el) => el.scrollIntoView({ block: 'center' }));
      await loose.dragTo(page.getByTestId('meas-group-head'));
      await expect.poll(async () => Object.keys((await getProject()).measureGroups?.members || {}).length, { timeout: 15_000 }).toBe(2);
    }
    // filters
    const all = await page.locator('[data-measure-row]').count();
    await page.getByTestId('meas-filter-kind-count').click();
    const counts = await page.locator('[data-measure-row]').count();
    expect(counts).toBeLessThan(all);
    await page.getByTestId('meas-filter-clear').click();
    await expect(page.locator('[data-measure-row]')).toHaveCount(all);
    note(`Matavimai: group Virtuvė, ${all} rows, Kiekiai filter → ${counts}`);
    await shot(page, 'w5b-matavimai-groups');
  });
});
