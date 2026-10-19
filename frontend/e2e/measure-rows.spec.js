/**
 * Measurements on sąmata rows, Kiekiai inline edit, „Kas pasikeitė — Atšaukti" (Pathon v3, track W4-A) on the
 * demo project (demo-objektas_h).
 *
 *  - „Į eilutę…" from a Matavimai row puts a measured length on a Kiekiai line: kiekis = the program's number
 *    + 4,20 m, the line carries „iš matavimų" with „+ matavimas 4,20 m (lapas 1)"; switching it to „Atimti"
 *    takes it away, „Atšaukti" in the toast puts it back, „Nuimti" returns the program's number;
 *  - dragging a tray chip onto a Kiekiai line does the same; a count dropped on an m² line is refused and
 *    says why (nothing written);
 *  - a double-click on a line's number types it: Enter / Tab saves (Tab opens the next line), Esc cancels,
 *    the toast's „Atšaukti" puts the program's number back;
 *  - after „Perskaityti iš naujo" the one-line notice reads „Kas pasikeitė", and its „Atšaukti" puts the project
 *    back as it was before the read (through Versijos; the read state stays as „Prieš grąžinant").
 *
 * WRITES to the project — part of `npm run test:e2e`: every test starts from the guide's start state (the
 * suite's helpers restore it and prove it) plus two measurements this file seeds through the API; the suite's
 * teardown puts the pristine database back. €0: no Vision call, no paid route.
 */
import { expect } from './pw.js';
import { PROJECT, api, getProject } from './state.js';
import { it, note, openProject, restoreStart, shot, toast } from './helpers.js';

const test = it;
test.describe.configure({ mode: 'default' });
test.beforeEach(async () => { await restoreStart(); });

const DIST = 'e2e-atstumas';
const TYPE = 'e2e-rozetes';
const LINE = 'Grindjuosčių sumontavimas';
const LINE_2 = 'Grindjuosčių dažymas';
const AREA_LINE = 'Sienų glaistymas/dažymas';

/** A 4,20 m length on sheet 1 (its lane scale 1:115) and a count type with two marks, saved as the viewer saves them. */
async function seedMeasurements() {
  const p = await getProject();
  const at = new Date().toISOString();
  const measurements = [
    { id: DIST, kind: 'distance', page: 1, points: [{ x: 271.80195, y: 376.1635 }, { x: 375.38461538461536, y: 375.38461538461536 }], classification: '', color: '#2a6fb5', confidence: 'amber', source: 'user', created_at: at },
    { id: 'e2e-c1', kind: 'count', page: 1, typeId: TYPE, points: [{ x: 300, y: 300 }], classification: '', color: '#2a6fb5', confidence: 'amber', source: 'user', created_at: at },
    { id: 'e2e-c2', kind: 'count', page: 1, typeId: TYPE, points: [{ x: 320, y: 310 }], classification: '', color: '#2a6fb5', confidence: 'amber', source: 'user', created_at: at },
  ];
  const { updated_at: _u, ...rest } = p;
  await api(`/api/projects/${PROJECT}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...rest, measurements, countTypes: [{ id: TYPE, label: 'Rozetės', color: '#2a6fb5', shape: 'circle' }] }),
  });
}

const row = (p, label) => (p.darbu_sarasas || []).find((r) => r.aprasymas === label);
const round2 = (v) => Math.round(v * 100) / 100;
const lt = (v) => v.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
/** A Kiekiai line (its label span carries the label as its title). */
const family = (page, label) => page.locator('[role="treeitem"][data-qkey]', { has: page.locator(`span[title="${label}"]`) });

async function openKiekiai(page) {
  await page.getByTestId('right-tab-kiekiai').click();
  await expect(page.getByTestId('measure-tray')).toBeVisible();
}

test('„Į eilutę…" puts a measured length on a line — Atimti, Atšaukti, Nuimti', async ({ page }) => {
  await seedMeasurements();
  const before = row(await getProject(), LINE);
  await openProject(page);
  await page.locator(`[data-measure-row="meas:${DIST}"]`).getByTestId('measure-to-row').click();
  const picker = page.getByTestId('measure-row-picker');
  await expect(picker).toContainText('matavimas 4,20 m (lapas 1)');
  await expect(picker).toContainText('Rodomos eilutės, skaičiuojamos m');
  await picker.getByRole('textbox').fill('grindjuosčių sum');
  await picker.getByTestId('measure-row-option').filter({ hasText: LINE }).click();
  await expect(picker.getByRole('radio', { name: /Pridėti prie kiekio/ })).toBeChecked();
  await picker.getByTestId('measure-row-pick').click();
  const want = round2(before.kiekis + 4.2);
  await expect(toast(page, `matavimas 4,20 m (lapas 1) → „${LINE}“`)).toContainText(`${lt(before.kiekis)} m → ${lt(want)} m`);
  await expect.poll(async () => row(await getProject(), LINE)?.kiekis, { timeout: 15_000 }).toBe(want);
  const saved = row(await getProject(), LINE);
  expect(saved.kiekis_programos).toBe(before.kiekis);
  expect(saved.matavimai.map((l) => l.tekstas)).toEqual(['+ matavimas 4,20 m (lapas 1)']);
  expect(saved.roll_up.at(-1)).toMatchObject({ op: 'matavimas', value: want });
  await expect(page.locator(`[data-measure-row="meas:${DIST}"]`).getByTestId('measure-linked')).toHaveText(`→ ${LINE}`);
  note(`„Į eilutę…": ${LINE} ${lt(before.kiekis)} + 4,20 = ${lt(want)} m (3 clicks)`);

  // the Kiekiai line carries „iš matavimų"; its list switches how the length counts, with Atšaukti
  await openKiekiai(page);
  const line = family(page, LINE);
  await expect(line).toContainText(`${lt(want)} m`);
  await line.getByTestId('measured-chip').click();
  const list = page.getByTestId('measured-list');
  await expect(list).toContainText('+ matavimas 4,20 m (lapas 1)');
  await expect(list).toContainText(`Programa: ${lt(before.kiekis)} m → su matavimais ${lt(want)} m`);
  await shot(page, 'w4a-01-measured-chip');
  await list.getByRole('button', { name: 'Atimti', exact: true }).click();
  const less = round2(before.kiekis - 4.2);
  await expect(line).toContainText(`${lt(less)} m`);
  await toast(page, 'Atimti iš kiekio').getByRole('button', { name: 'Atšaukti' }).click();
  await expect(line).toContainText(`${lt(want)} m`);
  await expect.poll(async () => row(await getProject(), LINE)?.kiekis, { timeout: 15_000 }).toBe(want);
  // Nuimti: the program's number comes back, the chip goes
  await line.getByTestId('measured-chip').click();
  await page.getByTestId('measured-list').getByTestId('measured-unlink').click();
  await expect(line).toContainText(`${lt(before.kiekis)} m`);
  await expect(line.getByTestId('measured-chip')).toHaveCount(0);
  await expect.poll(async () => row(await getProject(), LINE)?.kiekis, { timeout: 15_000 }).toBe(before.kiekis);
  expect('matavimai' in row(await getProject(), LINE)).toBe(false);
  note('Atimti → Atšaukti → Nuimti: the program\'s number is back');
});

test('dragging a measurement chip onto a Kiekiai line; a count on an m² line is refused', async ({ page }) => {
  await seedMeasurements();
  const before = row(await getProject(), LINE_2);
  await openProject(page);
  await openKiekiai(page);
  const target = family(page, LINE_2);
  await page.getByTestId('measure-tray').locator(`[data-measure-drag="m:${DIST}"]`).dragTo(target);
  const want = round2(before.kiekis + 4.2);
  await expect(target).toContainText(`${lt(want)} m`);
  await expect(target.getByTestId('measured-chip')).toBeVisible();
  await expect.poll(async () => row(await getProject(), LINE_2)?.kiekis, { timeout: 15_000 }).toBe(want);
  note(`drag: ${LINE_2} ${lt(before.kiekis)} + 4,20 = ${lt(want)} m (1 drag)`);
  await shot(page, 'w4a-02-dragged');

  // the two Rozetės marks (vnt.) dropped on a line counted in m²: refused, said why, nothing written
  const area = family(page, AREA_LINE);
  const areaBefore = row(await getProject(), AREA_LINE).kiekis;
  await page.getByTestId('measure-tray').locator(`[data-measure-drag="type:${TYPE}"]`).dragTo(area);
  await expect(toast(page, 'Eilutė skaičiuojama m², o matavimas — vnt.')).toBeVisible();
  const p = await getProject();
  expect(Object.keys(p.measurementRows || {})).toEqual([`m:${DIST}`]);
  expect(row(p, AREA_LINE).kiekis).toBe(areaBefore);
});

test('Kiekiai inline edit: double-click, Tab to the next line, Esc, Enter, Atšaukti', async ({ page }) => {
  const before = row(await getProject(), LINE_2);
  await openProject(page);
  await page.getByTestId('right-tab-kiekiai').click();
  const line = family(page, LINE_2);
  await line.getByTestId('family-quantity').dblclick();
  const editor = page.getByTestId('quantity-editor');
  await expect(editor).toHaveAttribute('aria-label', `Kiekis: ${LINE_2}`);
  await editor.fill('80');
  await editor.press('Tab');
  // saved, and the next line's number is open
  await expect(line).toContainText('ranka');
  await expect(line).toContainText('80,00 m');
  await expect(editor).toBeVisible();
  const next = await editor.getAttribute('aria-label');
  expect(next).not.toBe(`Kiekis: ${LINE_2}`);
  await editor.press('Escape');
  await expect(editor).toHaveCount(0);
  await expect.poll(async () => row(await getProject(), LINE_2)?.kiekis, { timeout: 15_000 }).toBe(80);
  expect(row(await getProject(), LINE_2).manual_override).toBe(true);
  // the toast of that save puts the program's number back
  await toast(page, `„${LINE_2}“: ${lt(before.kiekis)} m → 80,00 m`).getByRole('button', { name: 'Atšaukti' }).click();
  await expect(line).toContainText(`${lt(before.kiekis)} m`);
  await expect(line).not.toContainText('ranka');
  await expect.poll(async () => row(await getProject(), LINE_2)?.kiekis, { timeout: 15_000 }).toBe(before.kiekis);
  // Esc changes nothing; Enter saves a decimal comma
  await line.getByTestId('family-quantity').dblclick();
  await editor.fill('1');
  await editor.press('Escape');
  await expect(line).toContainText(`${lt(before.kiekis)} m`);
  await line.getByTestId('family-quantity').dblclick();
  await editor.fill('77,5');
  await editor.press('Enter');
  await expect(line).toContainText('77,50 m');
  await expect.poll(async () => row(await getProject(), LINE_2)?.kiekis, { timeout: 15_000 }).toBe(77.5);
  note(`inline edit: ${LINE_2} → 80 (Tab → ${next.replace('Kiekis: ', '')}) → Atšaukti → 77,5 (2 actions + typing)`);
});

test('„Kas pasikeitė" after Perskaityti iš naujo — Atšaukti puts the project back as it was before the read', async ({ page }) => {
  await openProject(page);
  const before = await getProject();
  const startedAt = new Date();
  await page.getByTestId('detect-run-button').click();
  await page.getByTestId('detect-run-start-all').click();
  await expect(page.getByTestId('detect-run-headline')).toHaveText('Perskaityta · pritaikoma visam brėžiniui', { timeout: 120_000 });
  const banner = page.getByTestId('reread-diff-banner');
  await expect(banner).toContainText('Kas pasikeitė');
  await expect(page.getByTestId('reread-diff-undo')).toBeVisible();
  await expect.poll(async () => new Date((await getProject())._reread_diff?.at || 0) >= startedAt, { timeout: 30_000 }).toBe(true);
  const read = await getProject();
  expect(read._reread_diff.eilutes).toBeTruthy();
  await page.getByTestId('reread-diff-toggle').click();
  await shot(page, 'w4a-03-kas-pasikeite');
  await page.getByTestId('reread-diff-undo').click();
  // a save after the read asks first (it would go too); the read alone does not
  const dialog = page.getByRole('alertdialog');
  if (await dialog.isVisible({ timeout: 2000 }).catch(() => false)) {
    await expect(dialog).toContainText('Grąžinti projektą, koks buvo prieš perskaitymą?');
    await dialog.getByRole('button', { name: 'Atšaukti' }).click();
  }
  await expect(toast(page, 'Grąžinta, kaip buvo prieš perskaitymą')).toBeVisible({ timeout: 20_000 });
  const back = await getProject();
  expect(back._geometrija_perskaityta_at ?? null).toBe(before._geometrija_perskaityta_at ?? null);
  expect(back._reread_diff?.at ?? null).toBe(before._reread_diff?.at ?? null);
  const { versions } = await api(`/api/projects/${PROJECT}/versions`);
  expect(versions[0].saltinis).toBe('grazinta');
  if (!before._reread_diff) await expect(banner).toHaveCount(0);
  note('Kas pasikeitė → Atšaukti: back to the state before the read; the read kept as „Prieš grąžinant"');
});
