/**
 * Screens calmed (Pathon v3 B1-D, after the founder's first walk: „everything is everywhere, a person could
 * easily get lost"; „the sąmata page is all over the place").
 *
 * Asserts on the demo project (demo-objektas_h), at 1440×900 and 1280×720:
 *  - the right panel shows only the step's own tabs, the rest under one „Daugiau ▾" (a click menu; Esc
 *    closes it; a tab picked there works as before — Pokalbis opens on the drawing view, Patikra is a step);
 *  - Sąmata opens across the width (the drawing as the strip), the totals are one line, the checks /
 *    reminders / room summary / prices are one line each that opens in place, and the first sąmata row
 *    starts on the first screen;
 *  - at most one notice line stands above the panel content on every step;
 *  - the room list says the area source once in its header, not on every row;
 *  - the cookie bar (consent not yet given) sits over the bottom bar, never over the drawing.
 * Nothing here writes to the project (the cookie choice is browser-local).
 */
import { test, expect } from './pw.js';

const PROJECT = process.env.PATHON_E2E_PROJECT || 'demo-objektas_h';
const STEP_NAV = 'nav[aria-label="Projekto žingsniai"]';

async function openProject(page, path = `/project/${PROJECT}`, { cookie = false } = {}) {
  await page.addInitScript((k) => {
    try {
      localStorage.setItem('samatu_viewer_onboarded', '1');
      if (!k) {
        localStorage.setItem('pathon_cookie_consent', JSON.stringify({
          categories: { necessary: true, analytics: false, marketing: false }, timestamp: Date.now(),
        }));
      }
    } catch { /* storage blocked */ }
  }, cookie);
  await page.goto(path);
}

const waitForDrawing = (page) => expect(page.locator('[data-takeoff-viewer] [data-page-number]').first()).toBeAttached({ timeout: 60_000 });
const goToStep = (page, label) => page.locator(`${STEP_NAV} button`, { hasText: label }).first().click();
const tabIds = (page) => page.locator('[data-testid="right-panel"] [role="tab"]').evaluateAll((els) => els.map((e) => e.dataset.testid));

/** The notice lines standing above the panel's own content (folded notices count as their one line). */
const noticeLines = (page) => page.evaluate(() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const host = document.querySelector('[data-testid="workspace-notices"]');
  if (!host || !vis(host)) return 0;
  return [...host.querySelectorAll('[data-notice], [data-testid="notice-fold"]')]
    .filter(vis).filter((n) => !n.parentElement.closest('[data-notice]')).length;
});

test.describe('screens calmed — one step, its own panel, the sąmata as the page', () => {
  test('each step shows only its own tabs; „Daugiau" holds the rest and they still work', async ({ page }) => {
    await openProject(page);
    await waitForDrawing(page);
    expect(await tabIds(page)).toEqual(['right-tab-patalpos', 'right-tab-kiekiai']);
    const more = page.getByTestId('right-tab-more');
    await more.click();
    const menu = page.getByRole('menu', { name: 'Kiti skydelio skirtukai' });
    await expect(menu.getByRole('menuitem')).toHaveText(['Patikra', 'Sąmata', 'Pokalbis']);
    await page.keyboard.press('Escape');
    await expect(menu).toHaveCount(0);

    await goToStep(page, 'Patikra');
    await expect.poll(() => tabIds(page)).toEqual(['right-tab-patikra']);
    await goToStep(page, 'Sąmata');
    await expect.poll(() => tabIds(page)).toEqual(['right-tab-samata']);

    // a tab from the menu: Pokalbis opens on the drawing view and shows as the chosen tab
    await more.click();
    await menu.getByRole('menuitem', { name: 'Pokalbis' }).click();
    await expect.poll(() => page.locator('[data-testid="workspace"]').getAttribute('data-view')).toBe('brezinys');
    await expect(page.getByTestId('right-tab-pokalbis')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByRole('textbox', { name: 'Klausimas apie projektą' })).toBeVisible();
  });

  test('the room list says the area source once, not on every row', async ({ page }) => {
    await openProject(page);
    await waitForDrawing(page);
    await expect(page.getByTestId('rooms-source-line')).toContainText('Plotai iš eksplikacijos');
    await expect(page.locator('[data-testid="right-panel-patalpos"] [data-testid="provenance-chip-eksplikacija"]')).toHaveCount(0);
    await expect(page.getByTestId('room-row-area')).toHaveCount(11);
    // the area itself opens the eksplikacija row
    await page.getByTestId('room-row-area').first().click();
    await expect(page.getByTestId('eksplikacija-popover')).toContainText('iš eksplikacijos lentelės');
  });

  for (const [w, h] of [[1440, 900], [1280, 720]]) {
    test(`Sąmata is the page: one totals line, one line per box, rows on the first screen, ${w}×${h}`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h });
      await openProject(page, `/project/${PROJECT}?step=samata`);
      await expect(page.getByTestId('row-menu').first()).toBeVisible({ timeout: 60_000 });
      await expect(page.locator('[data-testid="workspace"]')).toHaveAttribute('data-canvas-mode', 'strip');
      // totals: one line
      const totals = await page.getByTestId('samata-totals').boundingBox();
      expect(totals.height, 'totals line height').toBeLessThanOrEqual(60);
      // the four boxes, each one closed line with its counts
      for (const id of ['sanity-notice', 'reminders-samata', 'samata-rooms-summary', 'samata-prices']) {
        const line = page.getByTestId(id);
        await expect(line).toBeVisible();
        await expect(line.getByRole('button').first()).toHaveAttribute('aria-expanded', 'false');
        expect((await line.boundingBox()).height, `${id} is one line`).toBeLessThanOrEqual(48);
      }
      await expect(page.getByTestId('samata-rooms-summary')).toContainText('11 patalpų · 143,27 m²');
      // the first row starts above the bottom bar
      const row = await page.getByTestId('row-menu').first().boundingBox();
      const bar = await page.locator('[data-testid="step-next"]').boundingBox();
      expect(row.y + row.height, 'first sąmata row on the first screen').toBeLessThanOrEqual(bar.y);
      expect(await noticeLines(page)).toBeLessThanOrEqual(1);
      // a line opens in place and folds again
      const rooms = page.getByTestId('samata-rooms-summary').getByRole('button').first();
      await rooms.click();
      await expect(page.getByTestId('samata-rooms-summary').locator('tbody tr')).toHaveCount(11);
      await rooms.click();
      await expect(page.getByTestId('samata-rooms-summary').locator('tbody tr')).toHaveCount(0);
    });

    test(`one line each: the free re-read offer and the room-list source in the 340 px panel, ${w}×${h}`, async ({ page }) => {
      // B2-B item 5 — the offer wrapped to 2–3 lines (93 px), the source header to 2 (53 px)
      await page.setViewportSize({ width: w, height: h });
      await openProject(page);
      await waitForDrawing(page);
      const offer = page.locator('[data-testid="free-reread-banner"]:visible');
      if (await offer.count()) {
        await expect(offer.first().getByRole('button', { name: 'Perskaityti' })).toBeVisible();
        expect((await offer.first().boundingBox()).height, 'offer height').toBeLessThanOrEqual(52);
      }
      const src = page.getByTestId('rooms-source-line');
      expect((await src.boundingBox()).height, 'source line height').toBeLessThanOrEqual(40);
      await page.getByTestId('rooms-source-help').click();
      await expect(page.getByTestId('rooms-source-hint')).toContainText('Spustelėkite patalpos plotą');
    });

    test(`the drawing's top-right buttons never wrap over the sheet title, Sąmata with the drawing, ${w}×${h}`, async ({ page }) => {
      // B2-B item 4 — at 1280 they wrapped under the sheet pill and covered the title
      await page.setViewportSize({ width: w, height: h });
      await openProject(page, `/project/${PROJECT}?step=samata`);
      await waitForDrawing(page);
      await page.getByRole('button', { name: /Rodyti brėžinį/ }).first().click();
      const row = page.locator('[data-chrome-top]');
      await expect.poll(async () => (await row.boundingBox())?.height ?? 999).toBeLessThanOrEqual(44);
      await expect(page.getByTestId('detect-run-button')).toBeVisible();
      await expect(page.getByTestId('revision-compare-button')).toBeVisible();
      const pill = await page.getByTestId('sheet-name').boundingBox();
      const btn = await page.getByTestId('detect-run-button').boundingBox();
      expect(btn.x, 'buttons sit right of the sheet name').toBeGreaterThanOrEqual(pill.x + pill.width);
    });

    test(`at most one notice line above the panel on every step, ${w}×${h}`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h });
      await openProject(page);
      await waitForDrawing(page);
      for (const label of ['Brėžinys', 'Sąmata', 'Siųsti']) {
        await goToStep(page, label);
        await page.waitForTimeout(500);
        const n = label === 'Siųsti'
          ? await page.locator('[data-testid="send-view"] [data-notice], [data-testid="send-view"] [data-testid="notice-fold"]').evaluateAll(
            (els) => els.filter((e) => e.getBoundingClientRect().height > 0 && !e.parentElement.closest('[data-notice]')).length)
          : await noticeLines(page);
        expect(n, `${label}: notice lines`).toBeLessThanOrEqual(1);
      }
    });

    test(`the cookie bar sits over the bottom bar, never over the drawing, ${w}×${h}`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h });
      await openProject(page, `/project/${PROJECT}`, { cookie: true });
      await waitForDrawing(page);
      const bar = page.getByTestId('cookie-banner');
      await expect(bar).toBeVisible();
      for (const name of ['Sutikti su visais', 'Tik būtinieji', 'Tvarkyti']) {
        await expect(bar.getByRole('button', { name })).toBeVisible();
      }
      const b = await bar.boundingBox();
      const canvas = await page.locator('[data-testid="viewer-canvas"]').boundingBox();
      expect(b.y, 'cookie bar top vs the drawing bottom').toBeGreaterThanOrEqual(canvas.y + canvas.height);
      expect(b.y + b.height).toBeLessThanOrEqual(h + 1);
      // B2-B: „Tvarkyti" puts the categories in the bar's own row — the bar does not grow over the drawing
      await bar.getByRole('button', { name: 'Tvarkyti' }).click();
      await expect(bar.getByRole('switch')).toHaveCount(3);
      const m = await bar.boundingBox();
      expect(m.y, 'categories open: bar top vs the drawing bottom').toBeGreaterThanOrEqual(canvas.y + canvas.height);
      expect(m.height).toBeLessThanOrEqual(b.height + 1);
      await bar.getByRole('switch', { name: 'Analitiniai' }).click();
      await expect(bar.getByRole('switch', { name: 'Analitiniai' })).toHaveAttribute('aria-checked', 'true');
      await bar.getByRole('button', { name: 'Tik būtinieji' }).click();
      await expect(bar).toHaveCount(0);
    });
  }
});
