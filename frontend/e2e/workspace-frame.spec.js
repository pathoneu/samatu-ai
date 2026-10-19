/**
 * Workspace frame (Pathon v3, wave 1, track W1-A) — the one workspace with four views.
 *
 * Asserts the frame contract on the demo project (demo-objektas_h, 8 sheets, 11 rooms):
 *  - the drawing is mounted ONCE and kept across all four views (same DOM element, still connected);
 *  - today's URLs land on the right view;
 *  - the right panel is 340 px, resizable 300–480, remembered in localStorage `samatu_panel_width`;
 *  - Sąmata opens with the rows across the width and the drawing as a 56 px strip (B1-D); „Rodyti brėžinį"
 *    brings it back beside the rows and „Išskleisti" collapses it again, never unmounting it;
 *  - the sheet list opens as a 56 px strip (name on click/focus, „Lapai"/T for the full rail);
 *  - the drawing's canvas takes ≥ 48 % of a 1440×900 window on Brėžinys;
 *  - every view's main button is on screen (1440×900 and 1280×720), the page never scrolls, the top bar
 *    is the same on all four, the step rail gives one cue per step;
 *
 * Written to merge into W0-A's Playwright suite (frontend/e2e): it uses relative URLs (the suite's
 * `baseURL`, e.g. http://localhost:5203 for the W1-A worktree) and needs the backend with auth off.
 * Nothing here writes to the project except the browser-local panel width.
 */
// Runs under the founder-guide suite's runner (npm run test:e2e): Playwright is resolved by ./pw.js.
import { test, expect } from './pw.js';

const PROJECT = process.env.PATHON_E2E_PROJECT || 'demo-objektas_h';
const STEP_NAV = 'nav[aria-label="Projekto žingsniai"]';

async function openProject(page, path = `/project/${PROJECT}`) {
  // The first-run coach marks and the cookie banner cover the frame; neither is what this suite tests.
  await page.addInitScript(() => {
    try { localStorage.setItem('samatu_viewer_onboarded', '1'); } catch { /* private mode */ }
  });
  await page.goto(path);
  const cookie = page.getByRole('button', { name: 'Tik būtinieji' });
  if (await cookie.isVisible({ timeout: 5000 }).catch(() => false)) await cookie.click();
}

async function waitForDrawing(page) {
  await expect(page.locator('[data-testid="viewer-canvas"]')).toBeVisible({ timeout: 30_000 });
  // a page has been laid out inside the viewport (EmbedPDF renders pages with data-page-number)
  await expect(page.locator('[data-takeoff-viewer] [data-page-number]').first()).toBeAttached({ timeout: 30_000 });
}

async function goToStep(page, label) {
  await page.locator(`${STEP_NAV} button`, { hasText: label }).first().click();
}

const workspaceView = (page) => page.locator('[data-testid="workspace"]').getAttribute('data-view');

test.describe('workspace frame — one workspace, four views', () => {
  test('the drawing is mounted once and kept across all four views', async ({ page }) => {
    await openProject(page);
    await waitForDrawing(page);
    await page.evaluate(() => {
      window.__w1aViewer = document.querySelector('[data-takeoff-viewer]');
      window.__w1aRoot = document.querySelector('[data-testid="viewer-root"]');
    });
    const same = () => page.evaluate(() => ({
      viewer: window.__w1aViewer === document.querySelector('[data-takeoff-viewer]') && window.__w1aViewer.isConnected,
      root: window.__w1aRoot === document.querySelector('[data-testid="viewer-root"]') && window.__w1aRoot.isConnected,
    }));

    for (const [label, view] of [['Patikra', 'patikra'], ['Sąmata', 'samata'], ['Siųsti', 'siusti'], ['Brėžinys', 'brezinys']]) {
      await goToStep(page, label);
      await expect.poll(() => workspaceView(page)).toBe(view);
      expect(await same(), `after ${label}`).toEqual({ viewer: true, root: true });
    }
    // and back through the browser history
    await page.goBack();
    await expect.poll(() => workspaceView(page)).toBe('siusti');
    expect(await same(), 'after browser back').toEqual({ viewer: true, root: true });
  });

  test("today's URLs land on the right view", async ({ page }) => {
    await openProject(page, `/project/${PROJECT}?step=samata`);
    await expect.poll(() => workspaceView(page)).toBe('samata');

    await page.goto(`/project/${PROJECT}/patikra`);
    await expect.poll(() => workspaceView(page)).toBe('patikra');
    await expect(page.locator('[data-testid="patikra-questions"]')).toBeVisible({ timeout: 30_000 });

    await page.goto(`/project/${PROJECT}/patikra?kambarys=04`);
    await expect.poll(() => workspaceView(page)).toBe('patikra');
    await expect(page.locator('[data-testid="right-panel-patikra"]')).toContainText('04', { timeout: 30_000 });

    await page.goto(`/project/${PROJECT}?step=siusti`);
    await expect.poll(() => workspaceView(page)).toBe('siusti');
  });

  test('the right panel is 340 px, resizable 300–480, and its width is remembered', async ({ page }) => {
    await openProject(page);
    await page.evaluate(() => { try { localStorage.removeItem('samatu_panel_width'); } catch { /* */ } });
    await page.reload();
    await waitForDrawing(page);
    const panel = page.locator('[data-testid="right-panel"]');
    const width = async () => Math.round((await panel.boundingBox()).width);
    expect(await width()).toBe(340);

    // drag the panel's left edge 60 px to the left → 400 px
    const handle = page.locator('[data-testid="right-panel-resizer"]');
    const hb = await handle.boundingBox();
    await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2);
    await page.mouse.down();
    await page.mouse.move(hb.x + hb.width / 2 - 30, hb.y + hb.height / 2, { steps: 4 });
    await page.mouse.move(hb.x + hb.width / 2 - 60, hb.y + hb.height / 2, { steps: 4 });
    await page.mouse.up();
    expect(await width()).toBe(400);
    expect(await page.evaluate(() => localStorage.getItem('samatu_panel_width'))).toBe('400');

    // the keyboard works on the focused handle, and both limits hold
    await handle.focus();
    await page.keyboard.press('ArrowLeft');
    expect(await width()).toBe(416);
    for (let i = 0; i < 10; i += 1) await page.keyboard.press('ArrowLeft');
    expect(await width()).toBe(480);
    for (let i = 0; i < 20; i += 1) await page.keyboard.press('ArrowRight');
    expect(await width()).toBe(300);

    // remembered across a reload
    await page.keyboard.press('ArrowLeft');
    await page.reload();
    await waitForDrawing(page);
    expect(await width()).toBe(316);
    await page.evaluate(() => { try { localStorage.removeItem('samatu_panel_width'); } catch { /* */ } });
  });

  test('the sheets sit in a 56 px strip; a click names the sheet; „Lapai" opens the full rail', async ({ page }) => {
    await openProject(page);
    await page.evaluate(() => { try { localStorage.removeItem('samatu_viewer_sheet_rail'); } catch { /* */ } });
    await page.reload();
    await waitForDrawing(page);
    const rail = page.locator('[data-testid="sheet-rail"]');
    await expect(rail).toHaveAttribute('data-mode', 'strip');
    expect(Math.round((await rail.boundingBox()).width)).toBe(56);

    // a click on a thumbnail opens that sheet and says its name beside the strip (not hover-only)
    await rail.locator('li[data-sheet-page="5"] button').click();
    await expect(page.locator('[data-testid="sheet-strip-label"]')).toContainText('lapas 5');
    await page.keyboard.press('Escape');
    await expect(page.locator('[data-testid="sheet-strip-label"]')).toHaveCount(0);

    await page.locator('[data-testid="sheet-rail-expand"]').click();
    await expect(rail).not.toHaveAttribute('data-mode', 'strip');
    expect(Math.round((await rail.boundingBox()).width)).toBe(232);
    // T toggles back to the strip, and the choice is remembered
    await page.keyboard.press('t');
    await expect(rail).toHaveAttribute('data-mode', 'strip');
    expect(await page.evaluate(() => localStorage.getItem('samatu_viewer_sheet_rail'))).toBe('strip');
  });

  test('the drawing gets at least 48 % of a 1440×900 window on Brėžinys', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openProject(page);
    await page.evaluate(() => {
      try { localStorage.removeItem('samatu_panel_width'); localStorage.removeItem('samatu_viewer_sheet_rail'); } catch { /* */ }
    });
    await page.reload();
    await waitForDrawing(page);
    const share = await page.evaluate(() => {
      const r = document.querySelector('[data-testid="viewer-canvas"]').getBoundingClientRect();
      return (r.width * r.height) / (innerWidth * innerHeight);
    });
    expect(share).toBeGreaterThanOrEqual(0.48);
  });

  for (const [w, h] of [[1440, 900], [1280, 720]]) {
    test(`every view keeps its main button on screen and the same top bar, ${w}×${h}`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h });
      await openProject(page);
      await waitForDrawing(page);
      for (const [label, view] of [['Brėžinys', 'brezinys'], ['Patikra', 'patikra'], ['Sąmata', 'samata'], ['Siųsti', 'siusti']]) {
        await goToStep(page, label);
        await expect.poll(() => workspaceView(page)).toBe(view);
        // the step's one big button: „… — į patikrą / į sąmatą / siųsti"; on Siųsti the export itself
        const primary = view === 'siusti'
          ? page.locator('[data-testid="send-view"] button').first()
          : page.locator('[data-testid="step-next"]');
        await expect(primary).toBeVisible();
        const box = await primary.boundingBox();
        expect(box.y + box.height, `${view}: main button bottom`).toBeLessThanOrEqual(h);
        // nothing scrolls the page: the frame is one screen high
        expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight + 1), `${view}: page scroll`).toBe(true);
        // the same top bar (name, totals, Prielaidos/Nustatymai, Versijos) on all four
        await expect(page.locator('[data-testid="project-frame"] > div').first()).toContainText('Versijos');
        // one cue per step: the active step is in ink with its number, no icon beside it
        const active = page.locator(`${STEP_NAV} [aria-current="step"]`);
        await expect(active).toHaveAttribute('data-testid', `step-${view}`);
        expect(await active.locator('svg').count()).toBe(0);
      }
    });
  }

  test("Patikra draws on the workspace's drawing: one viewer, the check on it, a pick click reaches the room sheet", async ({ page }) => {
    await openProject(page);
    await waitForDrawing(page);
    await page.evaluate(() => { window.__w1aViewer = document.querySelector('[data-takeoff-viewer]'); });
    // the outline read is answered here (nothing is saved): it only has to prove the click got through
    const asked = [];
    await page.route('**/rooms/*/outline-at', async (route) => {
      asked.push(route.request().postDataJSON());
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'outside' }) });
    });
    await page.goto(`/project/${PROJECT}/patikra?kambarys=03`);
    await waitForDrawing(page);
    const pane = page.locator('[data-testid="canvas-slot"] [data-testid="room-drawing-pane"]');
    await expect(pane).toHaveAttribute('data-hosted', '1', { timeout: 30_000 });
    expect(await page.locator('[data-takeoff-viewer]').count(), 'no second viewer in the panel').toBe(1);

    await page.locator('[data-testid="outline-pick"]').click();
    await expect(page.locator('[data-testid="viewer-root"] [data-picking="1"]')).toBeVisible();
    const canvas = await page.locator('[data-testid="viewer-canvas"]').boundingBox();
    await page.mouse.click(canvas.x + canvas.width / 2, canvas.y + canvas.height / 2);
    await expect.poll(() => asked.length).toBe(1);
    expect(asked[0]).toHaveProperty('page');

    // leaving Patikra gives the drawing back: no check controls, the same viewer
    await goToStep(page, 'Brėžinys');
    await expect.poll(() => workspaceView(page)).toBe('brezinys');
    await expect(page.locator('[data-testid="room-drawing-pane"]')).toHaveCount(0);
    await expect(page.locator('[data-picking="1"]')).toHaveCount(0);
  });

  test('Sąmata opens across the width; the drawing comes back beside the rows and stays mounted behind the strip', async ({ page }) => {
    await openProject(page);
    await waitForDrawing(page);
    await page.evaluate(() => { window.__w1aViewer = document.querySelector('[data-takeoff-viewer]'); });
    await goToStep(page, 'Sąmata');
    const mode = () => page.locator('[data-testid="workspace"]').getAttribute('data-canvas-mode');
    // B1-D: the sąmata IS the page on its step — the drawing waits as the strip
    await expect.poll(mode).toBe('strip');
    const strip = await page.locator('[data-testid="viewer-root"]').boundingBox();
    expect(Math.round(strip.width)).toBe(56);
    await expect(page.locator('[data-testid="samata-expand"]')).toHaveText('Rodyti brėžinį');
    await page.locator('[data-testid="canvas-strip"]').click();
    expect(await mode()).toBe('split');
    await expect(page.locator('[data-testid="viewer-canvas"]')).toBeVisible();
    await page.locator('[data-testid="samata-expand"]').click();
    expect(await mode()).toBe('strip');
    expect(await page.evaluate(() => window.__w1aViewer === document.querySelector('[data-takeoff-viewer]'))).toBe(true);
  });
});
