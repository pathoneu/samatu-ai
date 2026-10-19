/**
 * Market readiness (Pathon v3, wave 7, track W7-A M6) — the „Pagalba" page and the viewer walkthrough
 * stepping aside while a dialog is open (it sat on the coach layer above every dialog and covered it).
 *
 * Runs in W0-A's suite (`npm run test:e2e`, servers already up — see founder-guide.spec.js).
 */
import { expect } from './pw.js';
import { it, openProject, restoreStart, shot, note } from './helpers.js';

const test = it;
test.describe.configure({ mode: 'default' });
test.beforeEach(async () => { await restoreStart(); });

const box = async (loc) => {
  const b = await loc.boundingBox();
  return b ? { x: b.x, y: b.y, w: b.width, h: b.height } : null;
};

test.describe('help and onboarding (M6)', () => {
  test('„Pagalba" is in the menu and explains checking, outlines, line styles and what is new', async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem('pathon_cookie_consent', JSON.stringify({
          categories: { necessary: true, analytics: false, marketing: false }, timestamp: Date.now(),
        }));
      } catch { /* storage blocked */ }
    });
    await page.goto('/dashboard');
    await page.getByRole('link', { name: /Pagalba/ }).first().click();
    await expect(page).toHaveURL(/\/pagalba$/);
    await expect(page.getByRole('heading', { level: 1, name: /Pagalba/ })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Kas naujo/ })).toBeVisible();
    // „Rodyti įvadą dar kartą" clears the walkthrough's done-flag
    await page.evaluate(() => localStorage.setItem('samatu_viewer_onboarded', '1'));
    await page.getByTestId('help-reset-intro').click();
    expect(await page.evaluate(() => localStorage.getItem('samatu_viewer_onboarded'))).toBeNull();
    await shot(page, 'w7a-pagalba');
  });

  test('the walkthrough steps aside while a dialog is open and comes back on the same step', async ({ page }) => {
    await openProject(page, { coach: true });
    const coach = page.getByTestId('viewer-coach-mark');
    await expect(coach).toBeVisible();
    await page.getByTestId('viewer-coach-next').click();
    await expect(coach).toHaveAttribute('data-coach-step', 'distance');

    // „Nustatymai" (project settings) opens a dialog over the drawing.
    await page.getByRole('button', { name: 'Nustatymai', exact: true }).click();
    const dialog = page.locator('[role="dialog"][data-state="open"], [aria-modal="true"], .fixed.inset-0.z-50, .fixed.inset-0.z-modal')
      .filter({ hasNot: page.getByTestId('viewer-coach-mark') }).first();
    await expect(dialog).toBeVisible();
    await shot(page, 'w7a-coach-with-dialog');
    await expect(coach, 'no walkthrough card over the dialog').toHaveCount(0);

    // Esc belongs to the dialog, not the walkthrough: the walkthrough is not marked done.
    await page.keyboard.press('Escape');
    if (await dialog.isVisible()) await page.getByRole('button', { name: /Atšaukti|Uždaryti|Close/ }).first().click();
    await expect(dialog).toHaveCount(0);
    await expect(coach).toBeVisible();
    await expect(coach).toHaveAttribute('data-coach-step', 'distance');
    expect(await page.evaluate(() => localStorage.getItem('samatu_viewer_onboarded'))).toBeNull();
    note(`coach card back at ${JSON.stringify(await box(coach))}`);
    await shot(page, 'w7a-coach-after-dialog');
  });
});
