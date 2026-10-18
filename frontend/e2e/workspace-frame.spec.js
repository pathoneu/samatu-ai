/**
 * Workspace frame (Pathon v3, wave 1, track W1-A) — the one workspace with four views.
 *
 * Asserts the frame contract on the demo project (demo-objektas_h, 8 sheets, 11 rooms):
 *  - the drawing is mounted ONCE and kept across all four views (same DOM element, still connected);
 *  - today's URLs land on the right view;
 *  - the right panel is 340 px, resizable 300–480, remembered in localStorage `samatu_panel_width`;
 *  - Sąmata „Išskleisti" collapses the drawing to a 56 px strip without unmounting it;
 *
 * Written to merge into W0-A's Playwright suite (frontend/e2e): it uses relative URLs (the suite's
 * `baseURL`, e.g. http://localhost:5203 for the W1-A worktree) and needs the backend with auth off.
 * Nothing here writes to the project except the browser-local panel width.
 */
import { test, expect } from '@playwright/test';

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

  test('Sąmata „Išskleisti" gives the rows the width and keeps the drawing mounted behind a strip', async ({ page }) => {
    await openProject(page, `/project/${PROJECT}?step=samata`);
    await waitForDrawing(page);
    await page.evaluate(() => { window.__w1aViewer = document.querySelector('[data-takeoff-viewer]'); });
    const mode = () => page.locator('[data-testid="workspace"]').getAttribute('data-canvas-mode');
    expect(await mode()).toBe('split');
    await page.locator('[data-testid="samata-expand"]').click();
    expect(await mode()).toBe('strip');
    const strip = await page.locator('[data-testid="viewer-root"]').boundingBox();
    expect(Math.round(strip.width)).toBe(56);
    await page.locator('[data-testid="canvas-strip"]').click();
    expect(await mode()).toBe('split');
    expect(await page.evaluate(() => window.__w1aViewer === document.querySelector('[data-takeoff-viewer]'))).toBe(true);
  });
});
