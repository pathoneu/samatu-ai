/**
 * Workspace frame (Pathon v3, wave 1, track W1-A) — the one workspace with four views.
 *
 * Asserts the frame contract on the demo project (demo-objektas_h, 8 sheets, 11 rooms):
 *  - the drawing is mounted ONCE and kept across all four views (same DOM element, still connected);
 *  - today's URLs land on the right view;
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
});
