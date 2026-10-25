/**
 * Phase 4 viewer tools (v4, 2026-10-25): the „Skaičius" (Mastelis pagal skaičių) line tool, the deep link to a room,
 * and the blank sąmata rows with their reason.
 *
 * The scale-line tests run on the demo project (demo-objektas_h) against the backend's real
 * `POST /api/projects/{id}/geometry/scale-line`: the person drags a line over a written dimension, the server reads
 * the string under it and stores the sheet's scale. WRITES to the database (a `page_scales` row) — the suite's
 * teardown puts the pristine database back. €0: no Vision call, no paid route.
 */
import { expect } from './pw.js';
import { api, getProject } from './state.js';
import { it, note, openProject, restoreStart, shot, sheetPoints, dragBetween } from './helpers.js';

const test = it;
test.describe.configure({ mode: 'default' });
test.beforeEach(async () => { await restoreStart(); });

/** The longest dimension string on sheet 1 the lane stored with its drawn line: {text, a, b} in display fractions. */
async function longestString(pageNr = 1) {
  const project = await getProject();
  let best = null;
  for (const r of project.patalpos || []) {
    for (const w of r._sienos || []) {
      for (const e of w.eilutes || []) {
        if (Number(e.page) !== pageNr || !Array.isArray(e.line_pct) || e.line_pct.length !== 2) continue;
        const len = Math.hypot(e.line_pct[1][0] - e.line_pct[0][0], e.line_pct[1][1] - e.line_pct[0][1]);
        if (!best || len > best.len) best = { len, text: String(e.text), a: e.line_pct[0], b: e.line_pct[1] };
      }
    }
  }
  if (!best) throw new Error(`no stored dimension string with a drawn line on sheet ${pageNr}`);
  return best;
}

/** A point `t` of the way from a to b. */
const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];

async function armScaleLine(page) {
  const tile = page.locator('[data-tool="scaleLine"]');
  await expect(tile).toBeVisible();
  await expect(tile).toBeEnabled();
  await tile.click();
  await expect(tile).toHaveAttribute('aria-pressed', 'true');
}

test('a line dragged over a written dimension sets the sheet scale — shown in the chip, kept until confirmed, Atšaukti removes it', async ({ page }) => {
  await openProject(page);
  const s = await longestString(1);
  const [p1, p2] = await sheetPoints(page, 1, [s.a, s.b]);
  await armScaleLine(page);

  const posted = page.waitForResponse((r) => /\/geometry\/scale-line$/.test(r.url()) && r.request().method() === 'POST');
  await dragBetween(page, p1, p2);
  const body = await (await posted).json();
  expect(body.status).toBe('ok');
  expect(body.scale.source_text).toBe(s.text);
  const ratio = Math.round(body.scale.m_per_pt / (0.0254 / 72));
  note(`Skaičius: line over „${s.text}" → 1:${ratio} (${body.scale.m_per_pt} m/pt)`);
  expect(Math.abs(ratio - 115) / 115, 'the sheet is drawn at about 1:115').toBeLessThan(0.08);

  // the line stays drawn, solid, until he confirms; one notice names the scale and the string
  await expect(page.locator('[data-scale-line-mark="ok"]')).toHaveCount(1);
  const notice = page.locator('[data-sonner-toast]').filter({ hasText: 'jūsų nubrėžta linija' });
  await expect(notice).toHaveCount(1);
  await expect(notice).toContainText(`„${s.text}“`);
  // the chip words the scale as his line
  await expect(page.getByTestId('scale-chip-root')).toContainText('jūsų linija');
  await shot(page, 'p4-scale-line-drawn');

  // Atšaukti: the line goes and the sheet's scale is what it was
  await notice.getByRole('button', { name: 'Atšaukti' }).click();
  await expect(page.locator('[data-scale-line-mark]')).toHaveCount(0);
  await expect(page.getByTestId('scale-chip-root')).not.toContainText('jūsų linija');
});

test('„Tinka" confirms: the line leaves the drawing and the scale stays', async ({ page }) => {
  await openProject(page);
  const s = await longestString(1);
  const [p1, p2] = await sheetPoints(page, 1, [s.a, s.b]);
  await armScaleLine(page);
  await dragBetween(page, p1, p2);
  await expect(page.locator('[data-scale-line-mark="ok"]')).toHaveCount(1);
  await page.locator('[data-sonner-toast]').filter({ hasText: 'jūsų nubrėžta linija' }).getByRole('button', { name: 'Tinka' }).click();
  await expect(page.locator('[data-scale-line-mark]')).toHaveCount(0);
  await expect(page.getByTestId('scale-chip-root')).toContainText('jūsų linija');
});

test('a line over empty paper: one notice with the reason and „Bandyti dar kartą"; the line stays dashed until the retry', async ({ page }) => {
  await openProject(page);
  // a stretch of empty paper at a sheet edge, whichever one is not under a control
  let line = null;
  for (const cand of [[[0.3, 0.02], [0.4, 0.02]], [[0.5, 0.985], [0.6, 0.985]], [[0.985, 0.5], [0.985, 0.6]], [[0.012, 0.45], [0.012, 0.52]]]) {
    try { line = await sheetPoints(page, 1, cand); break; } catch { /* covered or off the page: the next one */ }
  }
  expect(line, 'a free stretch of paper to drag over').toBeTruthy();
  const [p1, p2] = line;
  await armScaleLine(page);
  const posted = page.waitForResponse((r) => /\/geometry\/scale-line$/.test(r.url()) && r.request().method() === 'POST');
  await dragBetween(page, p1, p2);
  const body = await (await posted).json();
  expect(body.status).toBe('blank');
  expect(body.reason).toBeTruthy();

  await expect(page.locator('[data-scale-line-mark="blank"]')).toHaveCount(1);
  const notices = page.locator('[data-sonner-toast]');
  await expect(notices).toHaveCount(1);                          // never stacked
  await expect(notices.first()).toContainText(body.reason.slice(0, 25));
  await shot(page, 'p4-scale-line-miss');
  await notices.first().getByRole('button', { name: 'Bandyti dar kartą' }).click();
  await expect(page.locator('[data-scale-line-mark]')).toHaveCount(0);
  await expect(page.locator('[data-tool="scaleLine"]')).toHaveAttribute('aria-pressed', 'true');   // armed for the next try

  // the server stored nothing for a miss
  const stored = await api('/api/projects/demo-objektas_h/geometry/scale?page=1');
  expect(stored.scale.source).not.toBe('user_line');
});

// ── the deep link and the blank rows, on the local objektas_i (A) copy (skipped where that project is not stored) ──
const OBJEKTAS_I = '559e17ce-e97c-4cd0-a768-5fbf202f7d72';

async function openOther(page, suffix) {
  await page.addInitScript(() => {
    try {
      localStorage.setItem('samatu_viewer_onboarded', '1');
      localStorage.setItem('pathon_cookie_consent', JSON.stringify({
        categories: { necessary: true, analytics: false, marketing: false }, timestamp: Date.now(),
      }));
    } catch { /* storage blocked */ }
  });
  await page.goto(`/project/${OBJEKTAS_I}${suffix}`);
}

async function hasObjektasI() {
  try { await api(`/api/projects/${OBJEKTAS_I}`); return true; } catch { return false; }
}

test('/patikra?kambarys=<nr> opens the viewer on the room\'s own sheet, not on sheet 1', async ({ page }) => {
  test.skip(!(await hasObjektasI()), 'objektas_i (A) is not in this database');
  await openOther(page, '/patikra?kambarys=2-6');
  await expect.poll(() => page.evaluate(() => window.__pathonViewerPage), { timeout: 90_000 }).toBe(4);
  await expect(page.getByTestId('room-drawing-pane')).toBeVisible();
  await shot(page, 'p4-deep-link-room');
});

test('a blank sąmata row says why under itself and „Įrašyti" opens its quantity cell', async ({ page }) => {
  test.skip(!(await hasObjektasI()), 'objektas_i (A) is not in this database');
  await openOther(page, '?step=samata');
  const reasons = page.getByTestId('blank-row-reason');
  // Phase 3b: blank rows (and their reasons) exist only on a project read by the current lane; a stored project
  // is offered the free re-read first (LANE_VERSION 20) — one click, no Vision — and the rows appear after it
  const offer = page.getByTestId('free-reread-banner').getByRole('button', { name: 'Perskaityti', exact: true });
  if (await offer.isVisible({ timeout: 15_000 }).catch(() => false)) await offer.click();
  await expect(reasons.first()).toBeVisible({ timeout: 120_000 });
  const n = await reasons.count();
  expect(n, 'the blank rows of the re-read').toBeGreaterThan(20);
  // the materials that follow a blank work row carry the backend's sentence about that row
  await expect(reasons.filter({ hasText: 'pagal tą eilutę' }).first()).toBeVisible();
  note(`Blank sąmata rows with their reason: ${n}`);
  await reasons.first().scrollIntoViewIfNeeded();
  await shot(page, 'p4-blank-rows');
  const row = reasons.first().locator('xpath=ancestor::tr[1]');
  await row.getByTestId('blank-row-enter').click();
  await expect(row.locator('input[inputmode="decimal"]')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(row.locator('input[inputmode="decimal"]')).toHaveCount(0);
});
