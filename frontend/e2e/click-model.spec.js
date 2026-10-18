/**
 * Click model and chrome (Pathon v3, wave 1, track W1-B) — the tool cards, the mode pill, the cursor hint,
 * Esc as one step back, Space-pan, framing, the draft's right-click pop-up, the selection bar.
 *
 * Runs in W0-A's suite (`npm run test:e2e`, servers already up — see founder-guide.spec.js): every test
 * starts from the guide's start state (restoreStart) on demo-objektas_h, 8 sheets, 11 rooms, no measurement.
 * Canvas points come from the sheet's display frame (helpers.sheetPoints), never hard-coded pixels.
 */
import { expect } from './pw.js';
import { clickAt, focusRoom, it, openProject, restoreStart, sheetPoints, shot, toast, note } from './helpers.js';

const test = it;
test.describe.configure({ mode: 'default' });
test.beforeEach(async () => { await restoreStart(); });

// Room 02 Katilinė's wall corners (its vector outline, display frame) — the founder-guide spec uses them too.
const ROOM_02 = [[0.39086, 0.25178], [0.4564, 0.25164], [0.4564, 0.38361], [0.39086, 0.38361]];
// Three points inside room 04 for a draft (no snapping target needed).
const DRAFT_04 = [[0.50, 0.52], [0.58, 0.52], [0.58, 0.60]];

const box = async (loc) => {
  const b = await loc.boundingBox();
  return b ? { x: b.x, y: b.y, w: b.width, h: b.height } : null;
};
const overlaps = (a, b) => !!(a && b) && !(a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y);
const pressed = (page, id) => page.locator(`[data-tool="${id}"]`).getAttribute('aria-pressed');
// The draft's vertices — the start state has no measurement, so every circle on the measure layer is the draft.
const draftPoints = (page) => page.locator('div[data-page-number="1"] svg[aria-label="Matavimo sluoksnis"] circle').count();

test.describe('click model and chrome', () => {
  for (const [w, h] of [[1440, 900], [1280, 720]]) {
    test(`the tool cards fit at ${w}×${h}: labelled, inside the drawing, no page scroll`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h });
      await openProject(page);
      const canvas = await box(page.getByTestId('viewer-canvas'));
      const rail = await box(page.locator('[data-tool-rail]'));
      expect(rail.y).toBeGreaterThanOrEqual(canvas.y);
      expect(rail.y + rail.h, 'the rail ends inside the drawing').toBeLessThanOrEqual(canvas.y + canvas.h);
      expect(rail.x).toBeGreaterThanOrEqual(canvas.x);
      const scroll = await page.evaluate(() => {
        const r = document.querySelector('[data-tool-rail]');
        const d = document.documentElement;
        return { railSh: r.scrollHeight, railCh: r.clientHeight, sw: d.scrollWidth, cw: d.clientWidth, sh: d.scrollHeight, ch: d.clientHeight };
      });
      expect(scroll.railSh).toBe(scroll.railCh);
      expect(scroll.sw, 'no horizontal page scroll').toBe(scroll.cw);
      expect(scroll.sh, 'no vertical page scroll').toBe(scroll.ch);
      // icon AND word on every tool card
      for (const [id, word] of [['select', 'Žymėti'], ['perimeter', 'Perimetras'], ['calibrate', 'Mastelis'], ['walls', 'Sienos']]) {
        const tile = page.locator(`[data-tool="${id}"]`);
        await expect(tile).toContainText(word);
        expect(await tile.locator('svg').count()).toBeGreaterThan(0);
      }
      // the pages / zoom card and the search card never overlap the rail or each other
      const nav = await box(page.locator('[data-nav-cluster]'));
      const header = await box(page.locator('[data-canvas-header]'));
      expect(overlaps(nav, rail) || overlaps(header, rail) || overlaps(nav, header)).toBe(false);
      note(`${w}×${h}: rail ${Math.round(rail.h)} px of ${Math.round(canvas.h)} px`);
      await shot(page, `w1b-rail-${w}`);
    });
  }

  test('every tool is reachable by its key; layers by U and S', async ({ page }) => {
    await openProject(page);
    await page.mouse.move(700, 400);
    for (const [key, id] of [['1', 'select'], ['l', 'lasso'], ['h', 'pan'], ['2', 'distance'], ['3', 'area'], ['4', 'perimeter'], ['6', 'count'], ['f', 'findSimilar'], ['k', 'calibrate']]) {
      await page.keyboard.press(key);
      await expect(page.locator(`[data-tool="${id}"]`), `${key} arms ${id}`).toHaveAttribute('aria-pressed', 'true');
      await expect(page.getByTestId('mode-pill')).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(page.locator(`[data-tool="${id}"]`)).toHaveAttribute('aria-pressed', 'false');
    }
    // R — the room tool (W1-D): armed when wired, otherwise the card says why it is not yet
    const room = page.locator('[data-tool="room"]');
    await page.keyboard.press('r');
    if (await room.isDisabled()) {
      await expect(room).toHaveAttribute('aria-pressed', 'false');
      note('R registered, room tool not wired yet (W1-D)');
    } else {
      await expect(room).toHaveAttribute('aria-pressed', 'true');
      await page.keyboard.press('Escape');
    }
    for (const [key, id] of [['u', 'zones'], ['s', 'walls']]) {
      await page.keyboard.press(key);
      await expect(page.locator(`[data-tool="${id}"]`)).toHaveAttribute('aria-pressed', 'true');
      await page.keyboard.press(key);
      await expect(page.locator(`[data-tool="${id}"]`)).toHaveAttribute('aria-pressed', 'false');
    }
  });

  test('Esc on a 3-point draft removes one point at a time, then leaves the tool, then the room', async ({ page }) => {
    await openProject(page);
    await focusRoom(page, '04');
    await page.keyboard.press('3');
    for (const p of await sheetPoints(page, 1, DRAFT_04)) await clickAt(page, p);
    await expect.poll(() => draftPoints(page)).toBe(3);
    for (const left of [2, 1, 0]) {
      await page.keyboard.press('Escape');
      await expect.poll(() => draftPoints(page)).toBe(left);
      expect(await pressed(page, 'area'), 'the tool stays while a point is left').toBe('true');
    }
    await page.keyboard.press('Escape');
    await expect(page.locator('[data-tool="area"]')).toHaveAttribute('aria-pressed', 'false');
    await expect(page.getByTestId('selection-bar'), 'the room is still selected').toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('selection-bar')).toHaveCount(0);
    note('Esc: 3 → 2 → 1 → 0 points → tool off → room off');
  });

  test('Esc closes an open panel before it drops the selected room', async ({ page }) => {
    await openProject(page);
    await focusRoom(page, '04');
    await page.getByTestId('viewer-more').click();
    await page.getByTestId('scales-toggle').click();
    await expect(page.getByTestId('scale-overview')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('scale-overview')).toHaveCount(0);
    await expect(page.getByTestId('selection-bar')).toBeVisible();
  });

  test('Space held pans the drawing from a measure tool; the draft and the tool stay', async ({ page }) => {
    await openProject(page);
    await page.keyboard.press('2');
    const [p0] = await sheetPoints(page, 1, [DRAFT_04[0]]);
    await clickAt(page, p0);
    await expect.poll(() => draftPoints(page)).toBe(1);
    const vp = page.getByTestId('viewer-canvas');
    const before = await vp.evaluate((el) => el.scrollTop);
    const c = await box(vp);
    const start = { x: c.x + c.w * 0.6, y: c.y + c.h * 0.6 };
    await page.mouse.move(start.x, start.y, { steps: 3 });
    await page.keyboard.down(' ');
    await page.mouse.down();
    await page.mouse.move(start.x, start.y - 150, { steps: 10 });
    await page.mouse.up();
    await page.keyboard.up(' ');
    const after = await vp.evaluate((el) => el.scrollTop);
    expect(Math.abs((after - before) - 150), `scrolled ${after - before} px for a 150 px drag`).toBeLessThan(8);
    expect(await draftPoints(page), 'the draft kept its point').toBe(1);
    expect(await pressed(page, 'distance')).toBe('true');
    note(`Space-pan: ${after - before} px, draft kept`);
  });

  test('Shift+F frames the selected room in the window', async ({ page }) => {
    await openProject(page);
    await focusRoom(page, '04');
    const pg = page.locator('div[data-page-number="1"]');
    const w0 = (await box(pg)).w;
    await page.keyboard.press('Shift+F');
    await expect.poll(async () => (await box(pg)).w, { timeout: 10_000 }).toBeGreaterThan(w0 * 1.2);
    await page.waitForTimeout(800);
    const label = await box(page.locator('[data-room-label="04"]'));
    const c = await box(page.getByTestId('viewer-canvas'));
    expect(Math.abs(label.x + label.w / 2 - (c.x + c.w / 2))).toBeLessThan(c.w * 0.25);
    expect(Math.abs(label.y + label.h / 2 - (c.y + c.h / 2))).toBeLessThan(c.h * 0.3);
  });

  test('a distance is written on its second click; Shift + click carries the chain on', async ({ page }) => {
    await openProject(page);
    await page.keyboard.press('2');
    const pts = await sheetPoints(page, 1, ROOM_02);
    await clickAt(page, { x: pts[3].x + 2, y: pts[3].y - 2 });
    await clickAt(page, { x: pts[2].x + 2, y: pts[2].y - 2 });
    await expect(toast(page, 'Atstumas: 1,58 m')).toBeVisible();
    expect(await draftPoints(page)).toBeGreaterThan(0); // the committed line's vertices are drawn
    const committed = await draftPoints(page);
    await clickAt(page, pts[0]);
    await page.keyboard.down('Shift');
    await clickAt(page, pts[1]);
    await page.keyboard.up('Shift');
    expect(await draftPoints(page), 'the chain is still a draft').toBe(committed + 2);
    await clickAt(page, { x: pts[2].x - 3, y: pts[2].y + 3 });
    await expect(page.locator('[data-sonner-toast]').filter({ hasText: /^Atstumas: / }).last()).toBeVisible();
  });

  test('right-click while drawing offers Baigti / Atšaukti at the pointer; Esc closes only the pop-up', async ({ page }) => {
    await openProject(page);
    await page.keyboard.press('3');
    const pts = await sheetPoints(page, 1, DRAFT_04);
    for (const p of pts) await clickAt(page, p);
    await expect.poll(() => draftPoints(page)).toBe(3);
    const mid = { x: (pts[0].x + pts[2].x) / 2, y: (pts[0].y + pts[2].y) / 2 };
    await clickAt(page, mid, { button: 'right' });
    const menu = page.locator('[data-draft-menu]');
    await expect(menu).toBeVisible();
    await expect(menu.getByRole('menuitem')).toHaveCount(2);
    expect(await draftPoints(page), 'a right-click adds no point').toBe(3);
    await page.keyboard.press('Escape');
    await expect(menu).toHaveCount(0);
    expect(await draftPoints(page), 'Esc closed the pop-up, not a point').toBe(3);
    await clickAt(page, mid, { button: 'right' });
    await menu.getByRole('menuitem', { name: 'Baigti' }).click();
    await expect(page.locator('[data-sonner-toast]').filter({ hasText: /^Plotas: / })).toBeVisible();
  });

  test('the selection bar stands above the selected room with icon and text; the legend never covers the label', async ({ page }) => {
    await openProject(page);
    await focusRoom(page, '02');
    const bar = page.getByTestId('selection-bar');
    await expect(bar).toHaveAttribute('data-kind', 'room');
    const label = await box(page.locator('[data-room-label="02"]'));
    const b = await box(bar);
    expect(overlaps(b, label), 'the bar is not on the label').toBe(false);
    for (const id of ['outline-edit-start', 'outline-tool-split', 'outline-tool-merge', 'outline-tool-subtract', 'selection-exclude', 'selection-evidence']) {
      const btn = bar.getByTestId(id);
      await expect(btn).toBeVisible();
      expect(await btn.locator('svg').count(), `${id} has an icon`).toBeGreaterThan(0);
      expect((await btn.innerText()).trim().length, `${id} has a word`).toBeGreaterThan(3);
    }
    await page.keyboard.press('s');
    const legend = await box(page.locator('[data-layer-legend]'));
    expect(overlaps(legend, label), 'the legend is not on the selected label').toBe(false);
    expect(overlaps(legend, b), 'the legend is not on the bar').toBe(false);
    await shot(page, 'w1b-selection-bar');
  });

  test('the cursor hint follows the pointer and changes per mode', async ({ page }) => {
    await openProject(page);
    const c = await box(page.getByTestId('viewer-canvas'));
    const at = { x: c.x + c.w * 0.55, y: c.y + c.h * 0.5 };
    await page.mouse.move(at.x, at.y, { steps: 3 });
    await expect(page.getByTestId('cursor-hint'), 'nothing at rest').toHaveCount(0);
    await page.keyboard.press('2');
    await page.mouse.move(at.x + 4, at.y + 4, { steps: 2 });
    const hint = page.getByTestId('cursor-hint');
    await expect(hint).toHaveText('Spustelėkite pradžią');
    const h1 = await box(hint);
    expect(h1.x).toBeGreaterThan(at.x);
    await page.mouse.move(at.x + 80, at.y + 40, { steps: 4 });
    await expect.poll(async () => (await box(hint)).x).toBeGreaterThan(h1.x + 60);
    await page.keyboard.press('3');
    await page.mouse.move(at.x + 70, at.y + 30, { steps: 2 });
    await expect(hint).toHaveText('Spustelėkite pirmą kampą');
    await page.keyboard.press('Escape');
    await page.mouse.move(at.x, at.y, { steps: 2 });
    await expect(page.getByTestId('cursor-hint')).toHaveCount(0);
  });

  test('the pill shows only the active mode', async ({ page }) => {
    await openProject(page);
    await page.keyboard.press('6');
    const pill = page.getByTestId('mode-pill');
    await expect(pill).toHaveAttribute('data-mode', 'count');
    await expect(pill).toContainText('Kiekis');
    await page.keyboard.press('2');
    await expect(pill).toHaveAttribute('data-mode', 'distance');
    await expect(pill).not.toContainText('Kiekis');
    await expect(page.getByTestId('mode-pill')).toHaveCount(1);
    const strip = await box(page.getByTestId('sheet-rail'));
    expect(overlaps(await box(pill), strip), 'the pill never covers the sheet strip').toBe(false);
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('mode-pill')).toHaveCount(0);
  });

  test('the Patikra check view stands the tools down', async ({ page }) => {
    await openProject(page);
    await page.keyboard.press('2');
    await expect(page.locator('[data-tool="distance"]')).toHaveAttribute('aria-pressed', 'true');
    // an in-app navigation (the drawing stays mounted, W1-A) to room 04's sheet — the check view borrows the viewer
    await page.evaluate(() => {
      window.history.pushState({}, '', '/project/demo-objektas_h/patikra?kambarys=04');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await expect(page.locator('[data-testid="canvas-slot"] [data-testid="room-drawing-pane"]')).toBeVisible({ timeout: 60_000 });
    await expect(page.locator('[data-tool-rail]'), 'no tool cards on the check view').toHaveCount(0);
    await expect(page.getByTestId('mode-pill'), 'no armed tool').toHaveCount(0);
    await page.goBack();
    await expect(page.locator('[data-tool="distance"]')).toHaveAttribute('aria-pressed', 'false');
  });

  test('the first-run coach card stands beside its tool card', async ({ page }) => {
    await openProject(page, { coach: true });
    const card = page.getByTestId('viewer-coach-mark');
    await expect(card).toBeVisible({ timeout: 15_000 });
    await page.waitForTimeout(600);
    const c = await box(card);
    const tile = await box(page.locator('[data-coach="calibrate"]'));
    expect(c.x).toBeGreaterThanOrEqual(tile.x + tile.w);
    expect(c.y).toBeLessThan(tile.y + tile.h);
    expect(c.y + c.h).toBeGreaterThan(tile.y);
  });
});
