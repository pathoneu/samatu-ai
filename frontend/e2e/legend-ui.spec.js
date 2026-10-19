/**
 * „Pažymėti legendą" (Pathon v3, wave 2, track W2-B) on demo-objektas_h, on the servers already up (see
 * founder-guide.spec.js for the two commands; E2E_BASE_URL / E2E_API_URL for other ports):
 *
 *   B1–B3: G → the lighting plan's legend PROPOSED (dashed) → „Taip" → its rows counted → review (a mark removed
 *          on the drawing, a row dropped) → „Sukurti kiekius (N)" → hollow marks on the drawing, count types and
 *          sąmata rows that follow the marks → „Atšaukti" takes all of it away; one journal row per legend row.
 *   B5:    the schedule questions (v3 W3-A kinds) answered in Patikra — the demo corpus has no project whose
 *          stored blob asks one, so the list is the real server's plus two questions in the server's own shape.
 *
 * €0: the legend routes read the PDF's own text and paths; nothing calls a model.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect } from './pw.js';
import { it, openProject, restoreStart, shot, note, toast, sheetPoints, dragBetween, clickAt } from './helpers.js';
import { api, getProject, PROJECT } from './state.js';

const test = it;
test.describe.configure({ mode: 'default' });
test.beforeEach(async () => { await restoreStart(); });

const legendRows = (p) => (p.darbu_sarasas || []).filter((r) => r.legend_row_id && r.quantity_source === 'measurement_count');

async function poll(fn, ok, { timeout = 20_000, step = 400 } = {}) {
  const until = Date.now() + timeout;
  let last;
  while (Date.now() < until) {
    last = await fn();
    if (ok(last)) return last;
    await new Promise((r) => { setTimeout(r, step); });
  }
  return last;
}

test.describe('legend marking (W2-B)', () => {
  test('G proposes the legend, nothing exists before „Sukurti kiekius", marks and rows follow, Atšaukti removes them', async ({ page }) => {
    await openProject(page);
    // the lighting plan — sheet 3 carries the switch and luminaire legend
    await page.keyboard.press(']');
    await page.keyboard.press(']');
    await expect(page.locator('[data-nav-cluster]')).toContainText('3 iš 8');

    // B1: the tool card and the key
    await expect(page.getByTestId('viewer-legend-tool')).toBeVisible();
    await page.keyboard.press('g');
    await expect(page.getByTestId('legend-review-panel')).toBeVisible();
    await expect(page.getByTestId('right-panel-cover')).toBeVisible();
    const proposal = page.locator('[data-testid="legend-layer-3"] [data-testid="legend-proposal"]');
    await expect(proposal.first()).toBeVisible({ timeout: 60_000 });
    const pill = page.getByTestId('mode-pill');
    await expect(pill).toContainText('Tai legend');
    await expect(pill.locator('button', { hasText: /^Taip$/ })).toBeVisible();
    await expect(pill.getByRole('button', { name: 'Nubrėžti kitaip' })).toBeVisible();
    await shot(page, 'w2b-01-proposed');

    // nothing has been created by looking
    const before = await getProject();
    expect((before.measurements || []).length).toBe(0);
    expect(legendRows(before)).toHaveLength(0);

    await pill.locator('button', { hasText: /^Taip$/ }).click();
    const create = page.getByTestId('legend-create');
    await expect(create).toBeVisible({ timeout: 150_000 });
    const rows = page.getByTestId('legend-row');
    const nRows = await rows.count();
    expect(nRows).toBeGreaterThanOrEqual(10);
    note(`legend rows read on sheet 3: ${nRows}`);
    await shot(page, 'w2b-02-review');

    // B2: a mark removed on the drawing (✕ by click), a row dropped, a row renamed
    const marksOnSheet = page.locator('[data-testid="legend-layer-3"] [data-testid="legend-instance"]');
    const found = await marksOnSheet.count();
    expect(found).toBeGreaterThan(0);
    await marksOnSheet.first().dispatchEvent('click');
    await expect(marksOnSheet).toHaveCount(found - 1);
    const kept = page.locator('[data-testid="legend-row"][data-keep="1"]');
    const keptBefore = await kept.count();
    await kept.nth(1).getByTestId('legend-drop').click();
    await expect(kept).toHaveCount(keptBefore - 1);
    // a row with marks gets his own name
    const withMarks = kept.filter({ has: page.getByTestId('legend-row-count').filter({ hasText: /^[1-9]\d* vnt/ }) });
    const first = withMarks.first();
    const firstId = await first.getAttribute('data-row-id');
    await first.getByTestId('legend-rename').click();
    await page.getByTestId('legend-rename-input').fill('Jungiklis (mano pavadinimas)');
    await page.getByTestId('legend-rename-input').press('Enter');
    await expect(page.locator(`[data-row-id="${firstId}"]`)).toContainText('Jungiklis (mano pavadinimas)');
    // a row the drawing shows NO mark of, kept anyway: the panel says beside it that the sąmata row stays blank
    const zero = page.locator('[data-testid="legend-row"][data-keep="0"]')
      .filter({ has: page.getByTestId('legend-row-count').filter({ hasText: /^0 vnt/ }) }).first();
    const blankId = await zero.getAttribute('data-row-id');
    await zero.getByTestId('legend-keep').click();
    await expect(page.locator(`[data-row-id="${blankId}"] [data-testid="legend-row-blank"]`))
      .toContainText('legendoje yra, brėžinyje ženklų nerasta — suskaičiuokite „Kiekis“ įrankiu');
    // „Sukurti kiekius (N)" counts only the kept rows with at least one mark
    const n = await page.$$eval('[data-testid="legend-row"][data-keep="1"]', (els) => els.filter((el) => {
      const t = el.querySelector('[data-testid="legend-row-count"]')?.textContent || '';
      return /^[1-9]/.test(t.trim());
    }).length);
    expect(n).toBeGreaterThan(0);
    await expect(create).toHaveText(new RegExp(`Sukurti kiekius \\(${n}\\)`));
    await shot(page, 'w2b-02b-review-blank');

    // still nothing on the project
    expect((await getProject()).measurements || []).toHaveLength(0);

    await create.click();
    await expect(page.getByTestId('legend-review-panel')).toHaveCount(0);
    await expect(toast(page, 'Sukurta pagal legendą')).toBeVisible();
    const aiMarks = page.locator('[data-page-number="3"] [data-ai-mark]');
    await expect(aiMarks.first()).toBeVisible();
    await shot(page, 'w2b-03-created');

    // B3: the project carries the types, the marks and ONE live sąmata row per type
    const after = await poll(getProject, (p) => (p.measurements || []).length > 0 && legendRows(p).length === n
      && (p.darbu_sarasas || []).some((r) => r.legend_row_id === blankId));
    const types = (after.countTypes || []).filter((t) => t.legend_row_id);
    expect(types).toHaveLength(n);
    expect(types.find((t) => t.legend_row_id === firstId)?.label).toBe('Jungiklis (mano pavadinimas)');
    const marks = after.measurements.filter((m) => m.kind === 'count' && m.source === 'legenda');
    expect(marks.length).toBeGreaterThan(0);
    const lrows = legendRows(after);
    expect(lrows).toHaveLength(n);
    for (const r of lrows) {
      const count = marks.filter((m) => m.typeId === r.measure_type_id).length;
      expect(r.kiekis, r.aprasymas).toBe(count);
      // the row's ledger line (lib/measuredRows `matavimai`, the type linked with kaip „kiekis")
      expect(r.matavimai?.[0]?.tekstas).toMatch(/^suskaičiuota pagal legendą: eilutė „.+“, \d+ ženkl/);
      expect(String(r.id)).toMatch(/^rnk-legenda-/);
    }
    // the kept row with no mark: a BLANK row with the question — no count claimed
    const blank = (after.darbu_sarasas || []).find((r) => r.legend_row_id === blankId);
    expect(blank, 'blank sąmata row').toBeTruthy();
    expect(blank.kiekis).toBeNull();
    expect(blank._confidence_reason).toBe('Legendoje yra, brėžinyje ženklų nerasta — suskaičiuokite „Kiekis“ įrankiu');
    expect(blank.ledger_note_lt).not.toMatch(/ženkl(ai|as|ų) lape/);
    expect(blank.matavimai ?? null).toBeNull();
    note(`created: ${n} count types, ${marks.length} marks, ${lrows.length} sąmata rows`);

    // the journal: one „legenda" row per countable legend row he judged
    const journal = await poll(() => api(`/api/projects/${PROJECT}/corrections`),
      (j) => (j.corrections || []).filter((c) => c.source === 'legenda').length >= n);
    const legendJournal = (journal.corrections || []).filter((c) => c.source === 'legenda');
    expect(legendJournal.length).toBeGreaterThanOrEqual(n);
    expect(legendJournal.some((c) => /legendos eilutę „Jungiklis \(mano pavadinimas\)“ patvirtinote/.test(c.sentence || c.text || ''))).toBeTruthy();
    expect(legendJournal.some((c) => /atmetėte/.test(c.sentence || c.text || ''))).toBeTruthy();
    note(`journal rows (legenda): ${legendJournal.length}`);

    // Undo: the marks, the types and the rows go
    await toast(page, 'Sukurta pagal legendą').getByRole('button', { name: 'Atšaukti' }).click();
    await expect(aiMarks).toHaveCount(0);
    const undone = await poll(getProject, (p) => (p.measurements || []).length === 0 && !(p.darbu_sarasas || []).some((r) => r.legend_row_id));
    expect(undone.measurements || []).toHaveLength(0);
    expect((undone.countTypes || []).filter((t) => t.legend_row_id)).toHaveLength(0);
    expect(legendRows(undone)).toHaveLength(0);
    expect((undone.darbu_sarasas || []).filter((r) => r.legend_row_id)).toHaveLength(0);
    await shot(page, 'w2b-04-undone');
  });

  test('Esc leaves the tool with nothing created; „Nubrėžti kitaip" asks for a box', async ({ page }) => {
    await openProject(page);
    await page.keyboard.press(']');
    await page.keyboard.press(']');
    await page.keyboard.press('g');
    const pill = page.getByTestId('mode-pill');
    await expect(pill.getByRole('button', { name: 'Nubrėžti kitaip' })).toBeVisible({ timeout: 60_000 });
    await pill.getByRole('button', { name: 'Nubrėžti kitaip' }).click();
    await expect(page.getByTestId('legend-review-panel')).toContainText('Tempdami apveskite legendą');
    await expect(page.locator('[data-testid="legend-proposal"]')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('legend-review-panel')).toHaveCount(0);
    await expect(page.getByTestId('right-tab-patalpos')).toBeVisible();
    expect((await getProject()).measurements || []).toHaveLength(0);
  });
});

// ── B1-B (2026-10-19): „it does not get calculated when I mark something" — every path ends in a sentence ─────

const BOX_EMPTY = 'Šiame rėmelyje legendos nėra — pažymėkite legendą su ženklais ir tekstu';

async function toSheet(page, n) {
  for (let i = 1; i < n; i += 1) await page.keyboard.press(']');
  await expect(page.locator('[data-nav-cluster]')).toContainText(`${n} iš`);
}

/** Drag a box on sheet `n` over display-frame fractions `b` = [x0, y0, x1, y1]. */
async function boxOn(page, n, b) {
  const [a, c] = await sheetPoints(page, n, [[b[0], b[1]], [b[2], b[3]]]);
  await dragBetween(page, a, c);
}

const outcome = (page) => page.getByTestId('legend-outcome');
const pill = (page) => page.getByTestId('mode-pill');

/** Open another project of the local corpus in the same viewer (coach marks and the cookie banner answered). */
async function openOther(page, id) {
  await page.addInitScript(() => {
    try {
      localStorage.setItem('samatu_viewer_onboarded', '1');
      localStorage.setItem('pathon_cookie_consent', JSON.stringify({ categories: { necessary: true, analytics: false, marketing: false }, timestamp: Date.now() }));
    } catch { /* storage blocked */ }
  });
  await page.goto(`/project/${id}`);
  await expect(page.locator('div[data-page-number="1"]')).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText('Kraunamas dokumentas', { exact: false })).toHaveCount(0, { timeout: 90_000 });
}

test.describe('legend paths (B1-B)', () => {
  test('(a) sheet 1 has no legend: it says where the legend is; a box on the room table, on empty paper, on the title block each end in a sentence', async ({ page }) => {
    await openProject(page);
    await page.keyboard.press('0');
    await page.keyboard.press('g');
    // within a second: the tool is on and says what it does
    await expect(page.getByTestId('legend-review-panel')).toBeVisible({ timeout: 1_000 });
    await expect(pill(page)).toContainText('Pažymėti legendą', { timeout: 1_000 });
    // no legend here: the sheets that carry one are named, with a way there
    await expect(page.getByTestId('legend-review-panel')).toContainText('Šiame lape legendos nėra. Legenda yra 2', { timeout: 30_000 });
    await expect(pill(page).getByRole('button', { name: 'Į 2 lapą' })).toBeVisible();
    await shot(page, 'b1b-a1-no-legend-here');

    // a box around the room table (text, no symbols): said, and the box stays on the drawing
    await boxOn(page, 1, [0.115, 0.54, 0.275, 0.675]);
    await expect(outcome(page)).toContainText(BOX_EMPTY);
    await expect(outcome(page)).toContainText('patalpų lentelė');
    await expect(pill(page)).toContainText(BOX_EMPTY);
    await expect(page.locator('[data-testid="legend-layer-1"] [data-testid="legend-drawn-box"][data-state="empty"]')).toBeVisible();
    await shot(page, 'b1b-a2-box-room-table');

    // empty paper
    await boxOn(page, 1, [0.12, 0.74, 0.38, 0.84]);
    await expect(outcome(page)).toContainText('Rėmelyje nėra jokio teksto');
    await shot(page, 'b1b-a3-box-empty-paper');

    // the title block: whatever is read is reviewed with a result sentence — never an empty panel
    await boxOn(page, 1, [0.42, 0.87, 0.66, 0.95]);
    await expect(page.getByTestId('legend-busy').or(outcome(page))).toBeVisible({ timeout: 1_000 });
    await expect(outcome(page)).toBeVisible({ timeout: 90_000 });
    note(`h sheet 1, title block box: ${await outcome(page).innerText()}`);
    await shot(page, 'b1b-a4-box-title-block');
    expect((await getProject()).measurements || []).toHaveLength(0);

    // „Į 2 lapą" from a fresh start: the legend there is proposed
    await page.keyboard.press('Escape');
    await page.keyboard.press('g');
    await pill(page).getByRole('button', { name: 'Į 2 lapą' }).click({ timeout: 30_000 });
    await expect(page.locator('[data-testid="legend-layer-2"] [data-testid="legend-proposal"]').first()).toBeVisible({ timeout: 30_000 });
  });

  test('(b, g) sheet 3 „Taip": counting shows within a second and ticks; the review opens with „Rasta … eilučių, … ženklai … lapuose"', async ({ page }) => {
    await openProject(page);
    await toSheet(page, 3);
    await page.keyboard.press('g');
    await expect(pill(page).locator('button', { hasText: /^Taip$/ })).toBeVisible({ timeout: 60_000 });
    // the count, slowed by 3 s here, so the ticking can be seen whatever the machine
    await page.route('**/legend/count', async (route) => { await new Promise((r) => { setTimeout(r, 3_000); }); await route.continue(); });
    const t0 = Date.now();
    await pill(page).locator('button', { hasText: /^Taip$/ }).click();
    await expect(page.getByTestId('legend-busy')).toContainText('Skaičiuoju…', { timeout: 1_000 });
    await expect(page.getByTestId('legend-busy')).toContainText('gali užtrukti iki minutės');
    await expect(pill(page)).toContainText('Skaičiuoju…', { timeout: 1_000 });
    note(`counting shown after ${Date.now() - t0} ms`);
    // the rows read are listed at once, numbers to follow
    expect(await page.locator('[data-testid="legend-rows-pending"] li').count()).toBeGreaterThanOrEqual(10);
    await expect(pill(page)).toContainText(/Skaičiuoju… [2-9] s/, { timeout: 4_000 });
    await shot(page, 'b1b-b1-counting');
    await expect(page.getByTestId('legend-create')).toBeVisible({ timeout: 150_000 });
    await expect(outcome(page)).toHaveAttribute('data-tone', 'ok');
    await expect(outcome(page)).toContainText(/^Rasta \d+ eilu(tė|tės|čių), \d+ ženkl(as|ai|ų) \d+ lap(e|uose)\.$/);
    await expect(pill(page)).toContainText(/Rasta \d+ eilu/);
    note(`h sheet 3 „Taip": ${await outcome(page).innerText()} after ${Math.round((Date.now() - t0) / 1000)} s`);
    await shot(page, 'b1b-b2-review-outcome');
  });

  test('(c, f) „Nubrėžti kitaip" + a box over the legend counts it; Esc mid-count leaves nothing behind and G starts again', async ({ page }) => {
    await openProject(page);
    await toSheet(page, 3);
    await page.keyboard.press('0');
    await page.keyboard.press('g');
    await expect(pill(page).getByRole('button', { name: 'Nubrėžti kitaip' })).toBeVisible({ timeout: 60_000 });
    await pill(page).getByRole('button', { name: 'Nubrėžti kitaip' }).click();
    await boxOn(page, 3, [0.062, 0.5, 0.226, 0.686]);
    await expect(page.getByTestId('legend-busy')).toBeVisible({ timeout: 1_000 });
    await expect(page.getByTestId('legend-busy')).toContainText('Skaičiuoju…', { timeout: 10_000 });
    // Esc while it counts: the tool closes, nothing is created, the late answer changes nothing
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('legend-review-panel')).toHaveCount(0);
    await expect(pill(page)).toHaveCount(0);
    await page.waitForTimeout(1_500);
    await expect(page.getByTestId('legend-review-panel')).toHaveCount(0);
    expect((await getProject()).measurements || []).toHaveLength(0);
    // G again: the proposal is back at once
    await page.keyboard.press('g');
    await expect(pill(page).locator('button', { hasText: /^Taip$/ })).toBeVisible({ timeout: 5_000 });
    // and the drawn box counted to the end gives the review
    await pill(page).getByRole('button', { name: 'Nubrėžti kitaip' }).click();
    await boxOn(page, 3, [0.062, 0.5, 0.226, 0.686]);
    await expect(page.getByTestId('legend-create')).toBeVisible({ timeout: 150_000 });
    await expect(outcome(page)).toContainText(/^Rasta \d+ eilu/);
    note(`h sheet 3 drawn box: ${await outcome(page).innerText()}`);
    await shot(page, 'b1b-c1-drawn-box-review');
  });

  test('(e) G with a room selected opens the tool; G in the middle of a measurement says to finish it first', async ({ page }) => {
    await openProject(page);
    await page.locator('[title^="Atidaryti psl."]').first().click();
    await page.keyboard.press('g');
    await expect(page.getByTestId('legend-review-panel')).toBeVisible({ timeout: 1_000 });
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('legend-review-panel')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'Atstumas', exact: true }).click();
    const [p] = await sheetPoints(page, 1, [[0.6, 0.45]]);
    await clickAt(page, p);
    await expect(pill(page).getByRole('button', { name: 'Baigti' })).toBeVisible();
    await page.keyboard.press('g');
    await expect(page.getByTestId('cursor-hint')).toContainText('Pirmiausia užbaikite', { timeout: 2_000 });
    // the measurement he is drawing is still there, and no legend tool took over
    await expect(pill(page).getByRole('button', { name: 'Baigti' })).toBeVisible();
    await expect(page.getByTestId('legend-review-panel')).toHaveCount(0);
    await shot(page, 'b1b-e1-g-during-draft');
  });

  test('a count that fails says so and „Bandyti dar kartą" counts again', async ({ page }) => {
    await openProject(page);
    await toSheet(page, 3);
    await page.keyboard.press('g');
    await expect(pill(page).locator('button', { hasText: /^Taip$/ })).toBeVisible({ timeout: 60_000 });
    let fail = true;
    await page.route('**/legend/count', async (route) => {
      if (fail) { await route.abort('failed'); return; }
      await route.continue();
    });
    await pill(page).locator('button', { hasText: /^Taip$/ }).click();
    await expect(outcome(page)).toHaveAttribute('data-tone', 'error', { timeout: 20_000 });
    await expect(outcome(page)).toContainText('Ženklų suskaičiuoti nepavyko: nepavyko pasiekti serverio — patikrinkite ryšį');
    await expect(pill(page)).toContainText('Ženklų suskaičiuoti nepavyko');
    await shot(page, 'b1b-x1-count-failed');
    fail = false;
    await page.getByTestId('legend-retry').click();
    await expect(page.getByTestId('legend-busy')).toContainText('Skaičiuoju…', { timeout: 1_000 });
    await expect(outcome(page)).toHaveAttribute('data-tone', 'ok', { timeout: 150_000 });
    await expect(outcome(page)).toContainText(/^Rasta \d+ eilu/);
  });

  test('the count tool: one mark placed by hand offers „Rasti visus tokius" — the program looks for the rest', async ({ page }) => {
    await openProject(page);
    // a door swing on sheet 1 (A4 portrait, PDF point 338,5 × 344 of 595 × 842), as W5-A's A8
    const fx = 338.52 / 595.28; const fy = 344 / 841.89;
    const [p] = await sheetPoints(page, 1, [[fx, fy]]);
    await page.mouse.move(p.x, p.y);
    await page.keyboard.press('6');
    await page.getByTestId('count-type-new-name').fill('Durys B1');
    await page.getByTestId('count-type-new-name').press('Enter');
    await expect(pill(page)).toContainText('Durys B1: 0 vnt.');
    await expect(pill(page).getByRole('button', { name: 'Rasti visus tokius' })).toHaveCount(0);
    await clickAt(page, p);
    await expect(pill(page)).toContainText('Durys B1: 1 vnt.');
    await expect(pill(page).getByRole('button', { name: 'Rasti visus tokius' })).toBeVisible();
    await shot(page, 'b1b-k1-count-offer');
    await pill(page).getByRole('button', { name: 'Rasti visus tokius' }).click();
    await expect(page.getByTestId('symbol-review-panel')).toBeVisible();
    await expect(page.getByTestId('symbol-type')).toHaveValue(/.+/, { timeout: 60_000 });
    await expect(page.getByTestId('symbol-progress')).toHaveCount(0, { timeout: 60_000 });
    note(`count tool → „Rasti visus tokius": ${await page.getByTestId('symbol-row').count()} found for review`);
    await shot(page, 'b1b-k2-find-similar');
    await page.keyboard.press('Escape');
  });

  test('objektas_g: G on sheet 1 says the legend is on sheet 5, goes there, „Taip" counts it', async ({ page }) => {
    test.setTimeout(300_000);
    await openOther(page, 'demo-objektas_g');
    await page.keyboard.press('g');
    await expect(page.getByTestId('legend-review-panel')).toBeVisible({ timeout: 1_000 });
    await expect(page.getByTestId('legend-review-panel')).toContainText('Legenda yra 5 lape', { timeout: 60_000 });
    await shot(page, 'b1b-g1-legend-elsewhere');
    await page.getByTestId('legend-goto').click();
    await expect(page.locator('[data-testid="legend-layer-5"] [data-testid="legend-proposal"]').first()).toBeVisible({ timeout: 60_000 });
    await pill(page).locator('button', { hasText: /^Taip$/ }).click();
    await expect(page.getByTestId('legend-busy')).toContainText('Skaičiuoju…', { timeout: 1_000 });
    await expect(page.getByTestId('legend-create')).toBeVisible({ timeout: 150_000 });
    await expect(outcome(page)).toContainText(/^Rasta \d+ eilu/);
    note(`objektas_g sheet 5: ${await outcome(page).innerText()}`);
    await shot(page, 'b1b-g2-review');
  });

  test('(d) objektas_c: a legend of swatches the reader cannot take glyphs from, and a legend of material samples only', async ({ page }) => {
    test.setTimeout(300_000);
    const pdf = findFixture(/Objektas C .*\.pdf$/);
    test.skip(!pdf, 'objektas_c PDF is not in docs/superpowers/fixtures of this checkout');
    const id = 'e2e-objektas_c';
    // created for this test only — the next test's restore takes it away (database and pdf_store)
    await api(`/api/projects/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, name: 'Objektas C (e2e)', tipas: 'interjeras', patalpos: [] }) });
    const form = new FormData();
    form.append('pdf_file', new Blob([fs.readFileSync(pdf)], { type: 'application/pdf' }), 'c.pdf');
    await api(`/api/projects/${id}/pdf`, { method: 'POST', body: form });
    await openOther(page, id);
    await page.keyboard.press('0');
    // sheet 6: the floor legend is swatches + words — boxed, it is said plainly that no legend rows are there
    await toSheet(page, 6);
    await page.keyboard.press('g');
    await expect(page.getByTestId('legend-review-panel')).toContainText(/legendos (nėra|neradau)/, { timeout: 90_000 });
    await boxOn(page, 6, [0.745, 0.11, 0.915, 0.225]);
    await expect(outcome(page)).toContainText(BOX_EMPTY, { timeout: 30_000 });
    note(`objektas_c sheet 6 box: ${await outcome(page).innerText()}`);
    await shot(page, 'b1b-d1-swatch-legend');
    // sheet 2: the proposed legend holds material samples only — no count to wait for, and it says why
    await page.keyboard.press('Escape');
    for (let i = 0; i < 4; i += 1) await page.keyboard.press('[');
    await expect(page.locator('[data-nav-cluster]')).toContainText('2 iš');
    await page.keyboard.press('g');
    await expect(pill(page).locator('button', { hasText: /^Taip$/ })).toBeVisible({ timeout: 90_000 });
    await pill(page).locator('button', { hasText: /^Taip$/ }).click();
    await expect(outcome(page)).toContainText('tik medžiagų ar linijų pavyzdžiai', { timeout: 30_000 });
    await expect(page.getByTestId('legend-review-panel')).toContainText('Vienetais skaičiuoti nėra ką');
    await shot(page, 'b1b-d2-samples-only');
  });
});

/** The first fixture PDF whose file name matches (the corpus PDFs are untracked, copied per checkout). */
function findFixture(re) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'docs', 'superpowers', 'fixtures');
  const walk = (dir) => {
    let out = null;
    for (const e of (fs.existsSync(dir) ? fs.readdirSync(dir, { withFileTypes: true }) : [])) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) out = out || walk(p);
      else if (re.test(e.name)) out = out || p;
    }
    return out;
  };
  return walk(root);
}

test.describe('schedule questions in Patikra (W2-B B5)', () => {
  test('reconcile and info are answered, recorded on the project, and the table is shown on the drawing', async ({ page }) => {
    const durys = {
      id: 'lentele_durys', kind: 'lentele_durys', answer: 'reconcile', unit: 'vnt.', field: '_lenteliu_sprendimai',
      title: 'Durų žiniaraštyje — 7 durys, sienose rasta 5. Kurios teisingos?',
      why: 'Durų žiniaraštyje (9 lapas) surašyta: D1 ×4, D2 ×3. Siūlau skaičiuoti taip, kaip nubraižyta.',
      proposed: 'brezinys', proposed_label: 'Kaip nubraižyta sienose — 5',
      choices: [{ value: 'brezinys', label: 'Kaip nubraižyta sienose — 5' }, { value: 'ziniarastis', label: 'Kaip žiniaraštyje — 7' }],
      items: [{ room_nr: '03', room_name: 'Koridorius', field: '_lenteliu_sprendimai', unit: 'vnt.', page: 2, drawn: 2, sentence: 'Sienose nubraižyta: 2 durys.' }],
      manual: [], listed: 7, drawn: 5,
      lentele: { page: 2, rect_pct: [0.6, 0.6, 0.9, 0.75], sentence: 'Durų žiniaraštis 2 lape.' },
    };
    const suma = {
      id: 'lentele_suma', kind: 'lentele_suma', answer: 'info', unit: 'm²', field: '_lenteliu_sprendimai',
      title: 'Eksplikacijos suma ir patalpų plotų suma skiriasi',
      why: 'Patalpų eksplikacijoje (2 lapas) parašyta „Iš viso" — 145,00 m², o projekto patalpų plotų suma — 143,27 m².',
      items: [{ room_nr: '', room_name: 'Iš viso', field: null, unit: 'm²', page: 2, rect_pct: [0.1, 0.1, 0.3, 0.2], sentence: '', lentele: 145, musu: 143.27 }],
      manual: [], lentele: { page: 2, rect_pct: [0.1, 0.1, 0.3, 0.2], sentence: '' },
    };
    await page.route('**/api/projects/*/questions*', async (route) => {
      expect(route.request().url()).toContain('lenteles=1');      // asked for by default now
      const res = await route.fetch();
      const body = await res.json();
      const decided = (await getProject())._lenteliu_sprendimai || {};
      const extra = [durys, suma].filter((q) => !decided[q.id]);
      await route.fulfill({ response: res, json: { ...body, questions: [...extra, ...(body.questions || [])] } });
    });
    await openProject(page, { suffix: '/patikra' });
    await page.getByTestId('question-rail-lentele_durys').click();
    const card = page.getByTestId('question-card-lentele_durys');
    await expect(card).toBeVisible({ timeout: 60_000 });
    await expect(card.getByTestId('reconcile-brezinys')).toHaveAttribute('aria-pressed', 'true');
    await expect(card.getByTestId('question-show-table')).toBeVisible();
    await card.getByTestId('question-show-table').click();
    await shot(page, 'w2b-05-reconcile');
    await card.getByTestId('reconcile-ziniarastis').click();
    await card.getByTestId('question-accept').click();
    await expect(toast(page, 'Kaip žiniaraštyje — 7')).toBeVisible();
    const p1 = await poll(getProject, (p) => p._lenteliu_sprendimai?.lentele_durys === 'ziniarastis');
    expect(p1._lenteliu_sprendimai.lentele_durys).toBe('ziniarastis');
    await expect(page.getByTestId('question-rail-lentele_durys')).toHaveCount(0);

    await page.getByTestId('question-rail-lentele_suma').click();
    const info = page.getByTestId('question-card-lentele_suma');
    await expect(info.getByTestId('question-info')).toContainText('143,27');
    await shot(page, 'w2b-06-info');
    await info.getByTestId('question-accept').click();
    const p2 = await poll(getProject, (p) => p._lenteliu_sprendimai?.lentele_suma === 'matyta');
    expect(p2._lenteliu_sprendimai).toMatchObject({ lentele_durys: 'ziniarastis', lentele_suma: 'matyta' });
    await expect(page.getByTestId('question-rail-lentele_suma')).toHaveCount(0);

    // Atšaukti on the last answer brings that question back
    await toast(page, 'Pažymėta, kad matėte').getByRole('button', { name: 'Atšaukti' }).click();
    await expect(page.getByTestId('question-rail-lentele_suma')).toBeVisible();
    const p3 = await poll(getProject, (p) => !p._lenteliu_sprendimai?.lentele_suma);
    expect(p3._lenteliu_sprendimai?.lentele_suma).toBeUndefined();
    note('schedule questions: reconcile + info answered and recorded, info undone');
  });
});
