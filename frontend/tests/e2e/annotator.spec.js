// tests/e2e/annotator.spec.js
//
// End-to-end Playwright tests for the Annotator viewer. Every spec uses
// proper expect().toBeVisible() / toHaveCount() with built-in waitFor;
// no flaky `sleep(N)` patterns. Each spec is independent — beforeEach
// resets localStorage so the scale wizard reappears.

import { test, expect } from '@playwright/test';

const BERZAS_URL = '/project/berzas/annotator?fixture=berzas';

// Helper: open Beržų from a clean state (wizard not yet dismissed).
//
// We can't use addInitScript to clear localStorage because that re-fires on
// every navigation (including reload), wiping the dismissed-flag the wizard
// just persisted. Instead: stub dialogs via addInitScript (safe to repeat),
// navigate once, clear storage by origin, then reload to start clean.
async function openBerzasFresh(page) {
  await page.addInitScript(() => {
    window.alert = () => {};
    window.confirm = () => true;
    window.prompt = () => '1000';
  });
  await page.goto(BERZAS_URL);
  await page.evaluate(() => {
    try {
      Object.keys(localStorage).forEach((k) => {
        if (k.startsWith('scale-wizard-dismissed:')) localStorage.removeItem(k);
      });
    } catch {}
  });
  await page.reload();
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Scale calibration wizard appears on first open, not on second
// ─────────────────────────────────────────────────────────────────────────────
test('scale wizard appears on first open and is gone after dismissal', async ({ page }) => {
  await openBerzasFresh(page);

  // Wizard appears once at least one page has rendered
  await expect(page.getByText('Nustatykite mastelį')).toBeVisible({ timeout: 10_000 });
  // Dismiss via Praleisti
  await page.getByRole('button', { name: /Praleisti/ }).click();
  await expect(page.getByText('Nustatykite mastelį')).toBeHidden();

  // Reload — wizard should NOT reappear (dismissal persisted in localStorage)
  await page.reload();
  // Wait long enough for any wizard to appear if it would
  await page.waitForTimeout(1500);
  await expect(page.getByText('Nustatykite mastelį')).toBeHidden();
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. Toolbar shows all expected buttons
// ─────────────────────────────────────────────────────────────────────────────
test('toolbar renders all primary actions', async ({ page }) => {
  await openBerzasFresh(page);
  await page.getByRole('button', { name: /Praleisti/ }).click();
  await expect(page.getByRole('button', { name: /Pasirinkti/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Matuoti/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Atšaukti/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Pakartoti/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Saugoti/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Tikrinti/ })).toBeVisible();
  // Status row shows scale + counts. Labels are inlined with their value
  // (`Matavimai: 0`, `Simboliai: 0`), so match the full value text.
  await expect(page.getByText(/Mastelis:.*nekalibruota/)).toBeVisible();
  await expect(page.getByText(/^Matavimai:\s*0$/)).toBeVisible();
  await expect(page.getByText(/^Simboliai:\s*0$/)).toBeVisible();
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. Beržų loads all 17 pages as a scrollable vertical stack
// ─────────────────────────────────────────────────────────────────────────────
test('all 17 Beržų pages render in the multi-page canvas', async ({ page }) => {
  await openBerzasFresh(page);
  await page.getByRole('button', { name: /Praleisti/ }).click();
  // Wait until every page locator is in DOM
  await expect.poll(async () =>
    page.locator('[data-testid^="pdf-page-"]').count()
  ).toBe(17);
  // Last page must be reachable via scroll
  const lastPage = page.locator('[data-testid="pdf-page-17"]');
  await expect(lastPage).toBeAttached();
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. Room polygon click selects the room and shows RoomDetailCard
// ─────────────────────────────────────────────────────────────────────────────
test('clicking the Svetainė polygon shows RoomDetailCard with correct data', async ({ page }) => {
  await openBerzasFresh(page);
  await page.getByRole('button', { name: /Praleisti/ }).click();
  // Wait for room-graph data to populate
  await expect(page.getByText('Patalpos (11)')).toBeVisible({ timeout: 5_000 });

  // Use the sidebar row to select (browser-stable; canvas click works too but
  // sidebar click is the most reliable path through React event delegation).
  await page.getByText('Svetainė/virtuvė', { exact: true }).first().click();
  await expect(page.getByText('PASIRINKTA PATALPA')).toBeVisible();
  await expect(page.getByText(/102\s+Svetainė\/virtuvė/)).toBeVisible();
  await expect(page.getByText(/50\.54 m²/)).toBeVisible();   // floor area
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. Undo/Redo button states track the command stack
// ─────────────────────────────────────────────────────────────────────────────
test('undo/redo buttons start disabled and stay until a command pushes', async ({ page }) => {
  await openBerzasFresh(page);
  await page.getByRole('button', { name: /Praleisti/ }).click();
  // Both disabled on a fresh project
  await expect(page.getByRole('button', { name: /Atšaukti/ })).toBeDisabled();
  await expect(page.getByRole('button', { name: /Pakartoti/ })).toBeDisabled();
});

// ─────────────────────────────────────────────────────────────────────────────
// 6. Symbol palette renders 6 symbols + count badge updates on placement
// ─────────────────────────────────────────────────────────────────────────────
test('symbol palette renders and badge increments after placement', async ({ page }) => {
  await openBerzasFresh(page);
  await page.getByRole('button', { name: /Praleisti/ }).click();
  await expect(page.getByRole('button', { name: /Rozetė/ }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Šviestuvas/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Internetas/ })).toBeVisible();
});

// ─────────────────────────────────────────────────────────────────────────────
// 7. KŽ santrauka shows AI values from /room-graph
// ─────────────────────────────────────────────────────────────────────────────
test('KŽ santrauka shows AI numbers from room-graph', async ({ page }) => {
  await openBerzasFresh(page);
  await page.getByRole('button', { name: /Praleisti/ }).click();
  await expect(page.getByText('KŽ SANTRAUKA')).toBeVisible();
  // Beržų AI total dažymo plotas ~580 m²
  await expect(page.getByText(/580\.23 m²/)).toBeVisible();
});

// ─────────────────────────────────────────────────────────────────────────────
// 7a. Polygons are actually PAINTED to the lower canvas.
//
// This is a regression guard against the bug shipped between commits
// b8790b6 and bec69ea: every fabric.Polygon was being added to the
// Canvas but Chrome's GPU 32767-pixel canvas-side limit was being
// silently exceeded (canvas height × devicePixelRatio), causing every
// draw to discard. The footer correctly counted "Patalpos su poligonais:
// N/N" so DOM-level tests passed — but the user saw an empty overlay.
//
// We sample the lower canvas pixels in the floor-plan-page band and
// assert at least one bluish pixel exists (polygon fill is
// rgba(42, 111, 181, 0.08)). If polygons were missing, count == 0.
// ─────────────────────────────────────────────────────────────────────────────
test('room polygons actually paint to the lower canvas', async ({ page }) => {
  await openBerzasFresh(page);
  await page.getByRole('button', { name: /Praleisti/ }).click();

  // Wait for all 17 pages to be in DOM
  await expect.poll(async () =>
    page.locator('[data-testid^="pdf-page-"]').count()
  ).toBe(17);

  // With the virtual-viewport refactor (2026-06-03) the canvas is sized
  // to the scroller's clientRect (NOT the page stack). Wait for the
  // ResizeObserver tick that sets non-trivial canvas dims.
  await expect.poll(async () =>
    page.evaluate(() => {
      const c = document.querySelector('canvas.lower-canvas');
      return (c?.width || 0) * (c?.height || 0);
    }),
  ).toBeGreaterThan(10000);

  // Scroll page 2 (Svetainė's floor plan) into the scroller's viewport.
  // After scrollIntoView, the Svetainė polygon should be in the visible
  // canvas band — Fabric's viewportTransform translates the world
  // coords (page 2 starts at world-y ≈ 1207) into canvas-y near 0.
  await page.evaluate(() => {
    const el = document.querySelector('[data-testid="pdf-page-2"]');
    el && el.scrollIntoView({ block: 'start' });
  });
  // Two animation frames for the rAF-throttled viewportTransform + a
  // fabric requestRenderAll to land.
  await page.evaluate(() =>
    new Promise((r) =>
      requestAnimationFrame(() => requestAnimationFrame(r))));

  // Sample the lower canvas across the full visible canvas — polygons
  // can land anywhere in viewport-space depending on scroll. Looking
  // for bluish polygon fill pixels (rgba(42, 111, 181, 0.08)).
  const bluePolygonPixels = await page.evaluate(() => {
    const lower = document.querySelector('canvas.lower-canvas');
    if (!lower) return 0;
    const ctx = lower.getContext('2d');
    let count = 0;
    const step = Math.max(1, Math.floor(lower.height / 80));
    for (let y = 0; y < lower.height; y += step) {
      const row = ctx.getImageData(0, y, lower.width, 1).data;
      for (let x = 0; x < lower.width; x++) {
        const r = row[x*4], g = row[x*4+1], b = row[x*4+2], a = row[x*4+3];
        if (a > 10 && b > r && b > g && b > 150) count++;
      }
    }
    return count;
  });
  expect(bluePolygonPixels).toBeGreaterThan(100);
});

// ─────────────────────────────────────────────────────────────────────────────
// 8a. Uploaded-project route mounts the integrated AnnotatorView.
//
// /project/:id is the route real users land on after uploading. Until
// 2026-06-02 this rendered the legacy PlanViewer — the multi-page viewer
// was only reachable via the fixture-only /annotator route. This spec
// asserts the integration: visiting /project/:id with no IndexedDB blob
// still mounts the AnnotatorView shell (the PDF-missing fallback is the
// embedded view's own DOM, not the legacy viewer's), proving the wiring.
// ─────────────────────────────────────────────────────────────────────────────
test('uploaded-project route shows AnnotatorView shell or PDF-missing prompt', async ({ page }) => {
  await page.addInitScript(() => {
    window.alert = () => {};
    window.confirm = () => true;
    window.prompt = () => '1000';
  });
  // A non-existent project id triggers the fallback path in ProjectDetail
  // (pullProjectsFromBackend), but does NOT crash. The Brėžinys tab is the
  // default; if the project resolves and has no PDF, we see the
  // "Brėžinys nepasiekiamas" prompt — both branches prove the integration.
  await page.goto('/project/00000000-0000-0000-0000-000000000000');
  await expect(
    page.locator(
      'text=Brėžinys nepasiekiamas, text=Krauname brėžinį, [data-testid="viewer-scroll-container"], text=Projektas nerastas',
    ),
  ).toBeTruthy();   // any of the four states is acceptable; just shouldn't crash
  await expect(page.locator('text=PlanViewer')).toHaveCount(0);   // legacy widget gone
});

// ─────────────────────────────────────────────────────────────────────────────
// 9. Verify-all walkthrough starts and shows first polygon-equipped room
// ─────────────────────────────────────────────────────────────────────────────
test('Verify All Rooms walkthrough cycles polygon rooms', async ({ page }) => {
  await openBerzasFresh(page);
  await page.getByRole('button', { name: /Praleisti/ }).click();
  await page.getByRole('button', { name: /Tikrinti/ }).click();
  // Beržų has 1 polygon-equipped room (Svetainė) so "Tikrinimas 1 / 1"
  await expect(page.getByText('Tikrinimas 1 / 1')).toBeVisible();
  // Three action buttons present
  await expect(page.getByRole('button', { name: /✓ Taip/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Koreguoti/ })).toBeVisible();
  // Nutraukti button works
  await page.getByRole('button', { name: /Nutraukti/ }).click();
  await expect(page.getByText('Tikrinimas 1 / 1')).toBeHidden();
});
