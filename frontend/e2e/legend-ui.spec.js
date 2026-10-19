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
import { expect } from './pw.js';
import { it, openProject, restoreStart, shot, note, toast } from './helpers.js';
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
    const first = kept.first();
    const firstId = await first.getAttribute('data-row-id');
    await first.getByTestId('legend-rename').click();
    await page.getByTestId('legend-rename-input').fill('Jungiklis (mano pavadinimas)');
    await page.getByTestId('legend-rename-input').press('Enter');
    await expect(page.locator(`[data-row-id="${firstId}"]`)).toContainText('Jungiklis (mano pavadinimas)');
    const n = keptBefore - 1;
    await expect(create).toHaveText(new RegExp(`Sukurti kiekius \\(${n}\\)`));

    // still nothing on the project
    expect((await getProject()).measurements || []).toHaveLength(0);

    await create.click();
    await expect(page.getByTestId('legend-review-panel')).toHaveCount(0);
    await expect(toast(page, 'Sukurta pagal legendą')).toBeVisible();
    const aiMarks = page.locator('[data-page-number="3"] [data-ai-mark]');
    await expect(aiMarks.first()).toBeVisible();
    await shot(page, 'w2b-03-created');

    // B3: the project carries the types, the marks and ONE live sąmata row per type
    const after = await poll(getProject, (p) => (p.measurements || []).length > 0 && legendRows(p).length === n);
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
    const undone = await poll(getProject, (p) => (p.measurements || []).length === 0 && legendRows(p).length === 0);
    expect(undone.measurements || []).toHaveLength(0);
    expect((undone.countTypes || []).filter((t) => t.legend_row_id)).toHaveLength(0);
    expect(legendRows(undone)).toHaveLength(0);
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
