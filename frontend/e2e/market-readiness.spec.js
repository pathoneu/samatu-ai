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
    await expect(coach).toHaveAttribute('data-coach-step', 'tools');

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
    await expect(coach).toHaveAttribute('data-coach-step', 'tools');
    expect(await page.evaluate(() => localStorage.getItem('samatu_viewer_onboarded'))).toBeNull();
    note(`coach card back at ${JSON.stringify(await box(coach))}`);
    await shot(page, 'w7a-coach-after-dialog');
  });
});

// B1-E (founder 2026-10-19): a one-sentence first-use hint per tool, used up by the first click.
test.describe('first-use hints (B1-E)', () => {
  test('the first time R or G is on, one sentence stands above the pointer hint; the first click uses it up', async ({ page }) => {
    await page.addInitScript(() => { try { localStorage.removeItem('samatu_first_use_seen'); } catch { /* blocked */ } });
    await openProject(page);
    const canvas = await page.getByTestId('viewer-canvas').boundingBox();
    const x = canvas.x + canvas.width * 0.3;
    const y = canvas.y + canvas.height * 0.85;
    await page.mouse.move(x, y);
    await page.keyboard.press('r');
    await page.mouse.move(x + 4, y + 4);
    const first = page.getByTestId('cursor-hint-first-use');
    await expect(first).toHaveText('Kontūras nubrėžiamas pagal sienas — patikrinkite ir išsaugokite.');
    await shot(page, 'b1e-first-use-room');
    await page.keyboard.press('Escape');
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('mode-pill')).toHaveCount(0);
    await page.keyboard.press('g');
    await page.mouse.move(x + 8, y + 8);
    await expect(first).toHaveText(/legendos ženklus/);
    await page.mouse.down();
    await page.mouse.up();
    await page.keyboard.press('Escape');
    await page.keyboard.press('Escape');
    await page.keyboard.press('g');
    await page.mouse.move(x + 12, y + 12);
    await expect(page.getByTestId('cursor-hint')).toBeVisible();
    await expect(first, 'used up after the first click').toHaveCount(0);
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem('samatu_first_use_seen')))).toContain('legend');
    await page.keyboard.press('Escape');
    note('first-use: R and G each one sentence, gone after use');
  });
});

// B1-E: „Nustatymai" in sections, one line per setting, per-room rows only where a room differs, Undo.
test.describe('Nustatymai grouped (B1-E)', () => {
  test('five collapsed sections; a change shows what moved and Atšaukti puts it back', async ({ page }) => {
    await openProject(page);
    await page.getByRole('button', { name: 'Nustatymai', exact: true }).click();
    const panel = page.getByTestId('settings-panel');
    await expect(panel).toBeVisible();
    for (const s of ['bendra', 'patalpos', 'angos', 'medziagos', 'pasirinkimai']) {
      await expect(page.getByTestId(`settings-section-${s}`)).toHaveAttribute('aria-expanded', 'false');
    }
    await expect(page.getByTestId('settings-section-bendra')).toContainText('Q2 — po matiniais dažais');
    await shot(page, 'b1e-settings-closed');

    await page.getByTestId('settings-section-bendra').click();
    const q2 = panel.getByRole('button', { name: 'Q2', exact: true });
    await expect(q2).toHaveAttribute('aria-pressed', 'true');
    await panel.getByRole('button', { name: 'Q3', exact: true }).click();
    const bar = page.getByTestId('settings-last-change');
    await expect(bar).toContainText('Pakeista: Glaistymo lygis Q3.');
    await expect(bar).toContainText(/Persiskaičiavo 2 eilutės · Glaistas sienoms .* \+[\d ,]+ kg/, { timeout: 30_000 });
    const up = /\+([\d ,]+) kg/.exec(await bar.innerText())[1];
    await shot(page, 'b1e-settings-changed');
    await page.getByTestId('settings-undo').click();
    await expect(bar).toContainText('Atšaukta: Glaistymo lygis Q3.');
    // Atšaukti recomputes back by exactly what the change moved
    await expect(bar).toContainText(`−${up} kg`, { timeout: 30_000 });
    await expect(q2).toHaveAttribute('aria-pressed', 'true');
    note(`Q2 → Q3: +${up} kg putty, Atšaukti: −${up} kg`);

    // the note: one sentence behind a „?" reached with the keyboard
    const line = panel.locator('[data-setting="glaistimo_lygis"]');
    await line.getByTestId('setting-note-toggle').focus();
    await page.keyboard.press('Enter');
    await expect(line.getByTestId('setting-note')).toHaveText('Aukštesnis lygis — daugiau glaisto ir šlifavimo darbo.');

    // per room: the value for all rooms first, a row only for the rooms that differ
    await page.getByTestId('settings-section-patalpos').click();
    const walls = panel.locator('[data-assumption^="walls_paint_override:"]');
    await expect(panel.locator('[data-setting="walls_paint_override"]')).toContainText('dažomos 9 iš 11');
    await expect(walls).toHaveCount(3);   // „Visoms patalpoms" + the two rooms left unpainted
    await expect(panel.locator('[data-assumption="walls_paint_override:01"]')).toBeVisible();
    await expect(panel.locator('[data-assumption^="lubu_auksciai:"]')).toHaveCount(1);   // every room 2,82 m
    await page.getByTestId('settings-rooms-lubu_auksciai').click();
    await expect(panel.locator('[data-assumption^="lubu_auksciai:"]')).toHaveCount(12);
    await shot(page, 'b1e-settings-open');
  });
});
