/**
 * Founder-guide smoke suite — walks „Founder review on localhost (waves 1–3, togal-v2)"
 * (docs/superpowers/plans/2026-10-16-togal-v2-program.md) on demo-objektas_h, one test per guide step
 * plus „Versijos" and „Sąmata › Eksportuoti" preview. The regression gate of the Pathon v3 rebuild.
 *
 * The servers must already be up (this suite starts nothing):
 *   cd backend  && SAMATU_AUTH_DISABLED=1 ../venv/bin/uvicorn main:app --port 8121
 *   cd frontend && VITE_BACKEND_URL=http://localhost:8121 npm run dev -- --port 5201
 *   (in a worktree whose node_modules is a symlink, give that Vite its own cacheDir — v3 programme doc)
 * then:
 *   cd frontend && npm run test:e2e        (runs workspace-frame.spec.js too)
 * Other ports: E2E_BASE_URL / E2E_API_URL. Another data folder: E2E_DATA_DIR. Start version: E2E_START_VERSION.
 *
 * State: global-setup.js takes a pristine snapshot of backend/data/samatu.db + pdf_store (SQLite backup
 * API, see state.js), derives the guide's start state (04 not yet merged, no scale confirmed) into
 * .state/start.db; every test restores it first and proves it through the API; global-teardown.js puts
 * the pristine snapshot back. No Vision call, no paid route, nothing sent to a third party.
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { expect } from './pw.js';
import { PROJECT, REPO, START_JSON, api, fingerprint, getProject, readJson, roomsByNr } from './state.js';
import {
  PYTHON_HELPER, centroid, clickAt, dragBetween, escapeRe, expectKiekiai, focusRoom, insidePolygon, it, loadGeometry, note,
  measRow, moreItem, openProject, restoreStart, roomRow, sheetPoints, shot, toast, viewerReady,
} from './helpers.js';

const test = it;
test.describe.configure({ mode: 'default' });
test.beforeEach(async () => { await restoreStart(); });

// The written dimension „996" on sheet 1 (room 01's wall; ends of its drawn line, display frame).
const DIM_996 = [[0.41482, 0.40998], [0.45765, 0.40998]];
// Room 08's wall corner nearest 02 (its vector outline) — a snap target for the vertex editor.
const ROOM_08_CORNER = [0.47435, 0.39031];
// Room 02 Katilinė's wall corners (its vector outline).
const ROOM_02 = [[0.39086, 0.25178], [0.4564, 0.25164], [0.4564, 0.38361], [0.39086, 0.38361]];
// A pendant lamp on sheet 3 (APŠVIETIMO PLANAS) and the box half-size in points.
const LAMP_3 = [0.7165, 0.3962];
const LAMP_HALF_PT = 4;
const LAMP_THRESHOLD = 0.98;
// The snap mark on a wall corner of the drawing: a 12 px square outline in the overlay's „editing" colour
// (W1-C paints it through a style token, so it is found by shape, not by a colour attribute).
const CORNER_MARK = 'svg rect[width="12"][height="12"][fill="none"][pointer-events="none"]';
// Where the guide's column is drawn inside 04 (checked against 04's outline below) and its size.
const COLUMN_CENTRE = [0.55, 0.56];
const COLUMN_M2 = 2.06;

/** Sujungti 04 → 05 exactly as the guide does it; asserts the numbers before and after the save. */
async function mergeRooms(page, project) {
  const r05 = roomsByNr(project)['05'];
  const target = r05._vieta ? [r05._vieta.cx, r05._vieta.cy] : centroid(r05.polygon_pct);
  await focusRoom(page, '04');
  await page.getByTestId('outline-tool-merge').click();
  const panel = page.getByTestId('outline-tool-panel');
  await expect(panel).toContainText('Spustelėkite gretimos patalpos kontūrą šiame lape');
  const [p] = await sheetPoints(page, 1, [target]);
  await clickAt(page, p);
  await expect(panel).toContainText('04 + 05 → 60,31 m² · lentelėje 26,31 + 35,50 = 61,81 m²');
  await expect(panel).toContainText('Sąmatoje 04 skaičiuos abiejų patalpų plotą (26,31 + 35,50 m² iš eksplikacijos) ir 05 angas (langai: 1, durys: 1)');
  await expect(page.getByTestId('merge-finish-warning')).toContainText('Patalpų apdaila skiriasi: 05 grindys parketas arba laminatas, 04 plytelės');
  await page.getByTestId('outline-tool-save').click();
  await expect(toast(page, 'Patalpa 05 prijungta prie 04 — abiejų plotai ir angos skaičiuojami patalpoje 04')).toBeVisible();
  await expect.poll(async () => fingerprint(await getProject()), { timeout: 30_000 })
    .toMatchObject({ a04: 61.81, merged05: '04', kampai: 489.76, lubos: 143.27 });
}

/** Atimti: a 2,06 m² column inside 04, „Kas atimama?" = kolona (its faces are walls, 4 corners). */
async function subtractColumn(page, project) {
  const r04 = roomsByNr(project)['04'];
  expect(insidePolygon(COLUMN_CENTRE, r04.polygon_pct), 'the column centre lies inside room 04').toBe(true);
  const scale = project.pageScalesDurable?.['1']?.metersPerPointX || 115 * 0.0254 / 72;
  const W = r04._vieta?.W || 595;
  const H = r04._vieta?.H || 842;
  const sidePt = Math.sqrt(COLUMN_M2) / scale;
  const hx = sidePt / W / 2;
  const hy = sidePt / H / 2;
  await focusRoom(page, '04');
  await page.getByTestId('outline-tool-subtract').click();
  const panel = page.getByTestId('outline-tool-panel');
  await expect(panel).toContainText('Tempkite stačiakampį patalpos viduje');
  const [a, b] = await sheetPoints(page, 1, [[COLUMN_CENTRE[0] - hx, COLUMN_CENTRE[1] - hy], [COLUMN_CENTRE[0] + hx, COLUMN_CENTRE[1] + hy]]);
  await dragBetween(page, a, b);
  await expect(panel.getByTestId('subtract-holes')).toContainText('1. 2,06 m²');
  await expect(panel).toContainText('60,31 m² − 2,06 m² = 58,25 m²');
  const kind = panel.getByTestId('subtract-hole-kind');
  await expect(kind).toHaveValue('sienos');
  await expect(kind.locator('option')).toHaveText(['kolona / šachta — sienos dažomos', 'anga grindyse / kita — sienų nėra']);
  await expect(panel).toContainText('Kolonos / šachtos (1) sienos pridedamos prie dažomų sienų ir grindjuosčių (+5,74 m sienų ilgio)');
  await page.getByTestId('outline-tool-save').click();
  await expect(toast(page, 'Patalpos 04 kontūras išsaugotas su 1 išpjova')).toBeVisible();
  await expect.poll(async () => fingerprint(await getProject()), { timeout: 30_000 })
    .toMatchObject({ a04: 61.81, merged05: '04', kampai: 501.04, lubos: 143.27 });
}

async function learnedCount(page) {
  const label = await page.getByTestId('learning-count').getAttribute('aria-label');
  return Number(/Įsiminta: (\d+)/.exec(label)[1]);
}

// ─────────────────────────────────────────────────────────────────────────────────────────────────────

test('1 coach marks + shortcuts guide', async ({ page }) => {
  await openProject(page, { coach: true, cookie: true });
  await page.getByRole('button', { name: 'Tik būtinieji' }).click();
  const steps = [['Mastelis', 'Toliau'], ['Atstumas', 'Toliau'], ['Taisyti kontūrą', 'Supratau']];
  for (const [i, [title, next]] of steps.entries()) {
    const card = page.getByRole('dialog', { name: `Įvadas: ${title}` });
    await expect(card).toBeVisible({ timeout: 15_000 });
    await expect(card).toContainText(`Žingsnis ${i + 1} iš 3`);
    await expect(card.getByTestId('viewer-coach-next')).toHaveText(next);
    await card.getByTestId('viewer-coach-next').click();
  }
  await expect(page.getByTestId('viewer-coach-mark')).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem('samatu_viewer_onboarded'))).toBe('1');
  // shown once per browser
  await page.reload();
  await viewerReady(page);
  await page.waitForTimeout(1500);
  await expect(page.getByRole('dialog', { name: /^Įvadas:/ })).toHaveCount(0);
  note('coach 3 steps, once per browser');

  await moreItem(page, 'viewer-shortcuts-open');
  const guide = page.getByTestId('shortcuts-guide');
  await expect(guide).toBeVisible();
  await expect(guide).toContainText('Spartieji klavišai');
  await expect(page.getByTestId('shortcuts-guide-pdf')).toHaveText('Atsisiųsti PDF');
  await expect(page.getByTestId('shortcuts-guide-pdf')).toBeEnabled();
  for (const row of ['Atstumas — matuoti metrais', 'Plotas — matuoti m²', 'Šis sparčiųjų klavišų sąrašas']) {
    await expect(guide).toContainText(row);
  }
  note('„?" → guide + „Atsisiųsti PDF"');
  await shot(page, '01-coach-shortcuts');
});

test('2 sheet rail: strip, groups, rename + undo, restore auto name, search LED', async ({ page }) => {
  await openProject(page);
  const rail = page.getByRole('complementary', { name: 'Brėžinio lapai' });
  // W1-A: the rail opens as a strip of numbered thumbnails; a click names the sheet beside it
  await expect(page.getByTestId('sheet-rail')).toHaveAttribute('data-mode', 'strip');
  await expect(rail.locator('li[data-sheet-page]')).toHaveCount(8);
  await expect(rail.locator('li[data-sheet-page="3"] button')).toHaveAccessibleName('3 · APŠVIETIMO PLANAS — Elektra, lapas 3');
  await rail.locator('li[data-sheet-page="5"] button').click();
  await expect(page.getByTestId('sheet-strip-label')).toContainText('lapas 5');
  await page.keyboard.press('Escape');
  await page.getByTestId('sheet-rail-expand').click();
  await expect(page.getByTestId('sheet-rail')).not.toHaveAttribute('data-mode', 'strip');
  const groups = [['Architektūra ir interjeras', 5], ['Elektra', 2], ['Vandentiekis ir nuotekos', 1]];
  for (const [name, n] of groups) await expect(rail.getByRole('button', { name: `${name} ${n}` })).toBeVisible();
  const sheets = [
    ['1', 'IŠDĖSTYMO PLANAS (su patalpų eksplikacija)', 'Aukšto planas'], ['5', 'LUBŲ PLANAS', 'Lubų planas'],
    ['6', 'SIENŲ DAŽYMO PLANAS', 'Aukšto planas'], ['7', 'GRINDŲ DANGŲ PLANAS', 'Aukšto planas'],
    ['8', 'PERTVARŲ PLANAS', 'Aukšto planas'], ['2', 'ROZEČIŲ PLANAS', 'Elektros planas'],
    ['3', 'APŠVIETIMO PLANAS', 'Elektros planas'], ['4', 'VANDENS ĮVADŲ PLANAS', 'Santechnikos planas'],
  ];
  for (const [n, name, type] of sheets) await expect(rail.getByRole('button', { name: `${n} ${name} ${type}`, exact: true })).toBeVisible();
  note('strip of 8 → full rail: groups 5 / 2 / 1, 8 sheets named + typed');

  // rename → toast „Atšaukti" → back
  await rail.getByRole('button', { name: 'Pervadinti lapą 5' }).click();
  await rail.getByRole('textbox', { name: 'Lapo pavadinimas' }).fill('LUBŲ PLANAS E2E');
  await rail.getByRole('button', { name: 'Išsaugoti' }).click();
  await toast(page, 'Lapas 5 pakeistas').getByRole('button', { name: 'Atšaukti' }).click();
  await expect(rail.getByRole('button', { name: '5 LUBŲ PLANAS Lubų planas', exact: true })).toBeVisible();
  // rename → „Atkurti automatinį"
  await rail.getByRole('button', { name: 'Pervadinti lapą 5' }).click();
  await rail.getByRole('textbox', { name: 'Lapo pavadinimas' }).fill('LUBŲ PLANAS E2E');
  await rail.getByRole('button', { name: 'Išsaugoti' }).click();
  await expect(rail.getByRole('button', { name: /^5 LUBŲ PLANAS E2E Lubų planas/ })).toBeVisible();
  await rail.getByRole('button', { name: 'Pervadinti lapą 5' }).click();
  await rail.getByRole('button', { name: 'Atkurti automatinį' }).click();
  await expect(toast(page, 'Lapui 5 grąžintas automatinis pavadinimas')).toBeVisible();
  await expect(rail.getByRole('button', { name: '5 LUBŲ PLANAS Lubų planas', exact: true })).toBeVisible();
  await expect.poll(async () => fingerprint(await getProject()).sheetOverrides, { timeout: 15_000 }).toBe(0);
  note('rename undone twice → sheet_overrides {}');

  // search „LED" → hits per sheet
  await page.getByRole('button', { name: /^Paieška/ }).click();
  await page.getByRole('textbox', { name: 'Paieška dokumente' }).fill('LED');
  const hits = (n) => rail.getByRole('listitem').filter({ has: page.getByRole('button', { name: new RegExp(`^${n} `) }) }).getByTestId('sheet-hits');
  await expect(hits(3)).toHaveText('26', { timeout: 30_000 });
  await expect(hits(5)).toHaveText('4');
  for (const n of [1, 2, 4, 6, 7, 8]) await expect(hits(n)).toHaveText('0');
  await expect(page.getByText(/^\d+ \/ 30$/)).toBeVisible();
  note('LED: lapas 3 = 26, lapas 5 = 4, total 30');
  await shot(page, '02-sheet-rail');
});

test('3 Perskaityti iš naujo — whole drawing, €0', async ({ page }) => {
  await openProject(page);
  const startedAt = new Date();
  const before = await api(`/api/projects/${PROJECT}/versions`);
  await page.getByTestId('detect-run-button').click();
  await expect(page.getByTestId('detect-run-start-all')).toHaveText('Perskaityti visus lapus (8)');
  await page.getByTestId('detect-run-start-all').click();
  await expect(page.getByTestId('detect-run-headline')).toHaveText('Perskaityta · pritaikoma visam brėžiniui', { timeout: 120_000 });
  await expect(page.getByTestId('detect-run-summary')).toHaveText(
    '11 kontūrų, 24 angos, 6 perimetrai iš matmenų, danga 11 iš 11. Jūsų pataisyti kontūrai (4) palikti.');
  const stages = page.getByTestId('detect-run-stages');
  for (const line of ['Mastelis iš matmenų: 1:115 (8 lap.)', '7 kontūrai iš sienų, jūsų pataisytų palikta: 4.',
    '24 angos (langų: 9, durų: 9).', '6 perimetrai iš matmenų.', 'Danga perskaityta 11 iš 11 patalpų.']) {
    await expect(stages).toContainText(line);
  }
  // the one-line re-read chip (W1-C): nothing moved; „Rodyti" opens today's read (writes nothing)
  const chipNotice = page.getByTestId('reread-diff-banner');
  await expect(chipNotice).toContainText('Brėžinys perskaitytas iš naujo');
  await expect(chipNotice).toContainText('skaičiai nepasikeitė');
  await page.getByTestId('reread-diff-toggle').click();
  await expect(chipNotice).toContainText('Skaičiai nepasikeitė — visos patalpos perskaitytos taip pat.');
  await expect(chipNotice).toContainText(startedAt.toLocaleDateString('lt-LT', { timeZone: 'Europe/Vilnius' }));
  await expect.poll(async () => new Date((await getProject())._reread_diff?.at || 0) >= startedAt, { timeout: 15_000 }).toBe(true);
  await expect.poll(async () => (await api(`/api/projects/${PROJECT}/versions`)).versions[0].id, { timeout: 30_000 })
    .toBeGreaterThan(before.versions[0].id);
  const after = await api(`/api/projects/${PROJECT}/versions`);
  expect(after.versions.some((v) => v.saltinis === 'perskaityta' && v.id > before.versions[0].id)).toBe(true);
  const fp = fingerprint(await getProject());
  expect(fp).toMatchObject({ a04: 26.31, kampai: 475.66, lubos: 143.27 });
  note('11 kontūrų · 24 angos · 6 perimetrai · danga 11/11 · pataisyti 4 · kampai 475,66 unchanged');
  await shot(page, '03-reread');
});

test('4 Masteliai: confirm all, check against 996, calibration suggests 1:100', async ({ page }) => {
  await openProject(page);
  // the scale chip at the drawing's bottom-left (W1-D ScaleChip; was the status bar's sentence)
  const chip = page.getByTestId('scale-chip');
  await expect(chip).toHaveAttribute('data-scale-state', 'spejamas');
  await expect(chip).toContainText('1:115');
  await moreItem(page, 'scales-toggle');
  const panel = page.getByTestId('scale-overview');
  await expect(panel).toContainText('0 patvirtinti · 8 spėjami · 0 nenustatyti');
  await expect(panel).toContainText('8 lapai su tuo pačiu spėjamu masteliu 1:115: 1, 2, 3, 4, 5, 6, 7, 8');
  await expect(panel.locator('[data-scale-row][data-scale-state="spejamas"]')).toHaveCount(8);
  await panel.getByTestId('scale-confirm-all').click();
  await expect(panel).toContainText('8 patvirtinti · 0 spėjami · 0 nenustatyti');
  await expect(panel.locator('[data-scale-row][data-scale-state="patvirtintas"]')).toHaveCount(8);
  await expect(chip).toHaveAttribute('data-scale-state', 'patvirtintas');
  await expect.poll(async () => fingerprint(await getProject()).confirmedScales, { timeout: 15_000 }).toBe(8);
  note('8 / 8 patvirtinti 1:115');

  // v3 W1-B (audit F3): Esc closes this panel too — one step back: point → tool → panel → selection
  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  // „Patikrinti": two clicks on the drawn line of „996"
  await loadGeometry(page, 1);
  await moreItem(page, 'scales-toggle');
  await panel.locator('[data-scale-row="1"]').getByRole('button', { name: 'Patikrinti' }).click();
  await page.getByRole('button', { name: 'Uždaryti mastelius' }).click();
  for (const p of await sheetPoints(page, 1, DIM_996)) await clickAt(page, p);
  const card = page.getByTestId('scale-check');
  await expect(card).toContainText('Mastelio patikra · lapas 1');
  const rows = card.getByRole('row');
  await expect(rows).toHaveText([
    'Užrašyta Pagal mastelį Skirtumas', '996 (1,00 m) 0,99 m −0,3 %', '600 (0,60 m) 0,60 m −0,2 %', '800 (0,80 m) 0,80 m −0,2 %',
  ].map((t) => new RegExp(`^${escapeRe(t).replace(/ /g, '\\s*')}$`)));
  note('996 → 0,99 m −0,3 % · 600 −0,2 % · 800 −0,2 %');
  await page.getByRole('button', { name: 'Uždaryti patikrą' }).click();
  await page.keyboard.press('Escape');

  // „Mastelis": two clicks + a real length → the nearest standard scale is offered (cancelled, nothing saved)
  await page.getByRole('button', { name: 'Mastelis', exact: true }).click();
  for (const p of await sheetPoints(page, 1, DIM_996)) await clickAt(page, p);
  await page.getByTestId('calib-length').fill('0,89');
  await expect(page.getByTestId('calib-suggestion')).toContainText('artimiausias standartinis 1:100');
  await expect(page.getByTestId('calib-round-standard')).toHaveAttribute('aria-label', 'Suapvalinti iki standartinio mastelio 1:100');
  await expect(page.getByTestId('calib-round-standard')).toBeChecked();
  await shot(page, '04-scales');
  await page.getByRole('button', { name: 'Atšaukti', exact: true }).click();
  await page.keyboard.press('Escape');
  await expect(chip).toHaveAttribute('data-scale-state', 'patvirtintas');
  await expect(chip).toContainText('1:115');
  note('calibration → artimiausias 1:100 (atšaukta)');
});

test('5 room tools: walls layer, vertex edit, split, merge 04+05, subtract a column', async ({ page }) => {
  await openProject(page);
  const project = await getProject();

  // walls / outlines / openings layer, openings labelled D / L with metres
  const pg1 = page.locator('div[data-page-number="1"]');
  await page.getByTestId('viewer-walls-layer').click();
  await expect(page.getByTestId('viewer-walls-layer')).toHaveAttribute('aria-pressed', 'true');
  await expect(pg1.locator('svg text').filter({ hasText: /^D \d,\d\d m$/ }).first()).toBeVisible();
  const labels = await pg1.locator('svg text').evaluateAll((els) => els.map((e) => e.textContent));
  const d = labels.filter((t) => /^D \d,\d\d m$/.test(t)).length;
  const l = labels.filter((t) => /^L \d,\d\d m$/.test(t)).length;
  note(`walls layer: D ${d}, L ${l}`);
  expect({ d, l }).toEqual({ d: 13, l: 9 });
  await page.getByTestId('viewer-walls-layer').click();
  await expect(pg1.locator('svg text').filter({ hasText: /^[DL] \d,\d\d m$/ })).toHaveCount(0);

  // „Taisyti kontūrą" (vertices): drag a corner, Z steps back, Esc leaves without saving
  await loadGeometry(page, 1);
  let outlineWrites = 0;
  page.on('request', (r) => { if (/\/rooms\/\d+\/outline/.test(r.url())) outlineWrites += 1; });
  await focusRoom(page, '02');
  await page.getByTestId('outline-edit-start').click();
  const readout = pg1.locator('svg text').filter({ hasText: /· lentelėje 6,90 m²$/ });
  await expect(readout).toHaveText('7,13 m² · 12,18 m · lentelėje 6,90 m²');
  // the snap target: the wall-solid corner (page geometry) next to room 08's outline corner
  const { walls_pct: walls } = await api(`/api/projects/${PROJECT}/pages/1/geometry`);
  const wallCorner = walls.flat().reduce((best, v) => (
    Math.hypot((v[0] - ROOM_08_CORNER[0]) * 595, (v[1] - ROOM_08_CORNER[1]) * 842)
      < Math.hypot((best[0] - ROOM_08_CORNER[0]) * 595, (best[1] - ROOM_08_CORNER[1]) * 842) ? v : best));
  const [corner, other] = await sheetPoints(page, 1, [ROOM_02[2], wallCorner]);
  // drag the corner to 3 px off that wall corner: the orange marker sits on the corner, the vertex lands on it
  await page.mouse.move(corner.x, corner.y, { steps: 4 });
  await page.mouse.down();
  await page.mouse.move(other.x + 3, other.y + 3, { steps: 14 });
  const snapMark = pg1.locator(CORNER_MARK);
  await expect(snapMark).toHaveCount(1);
  const sb = await snapMark.boundingBox();
  expect(Math.abs(sb.x + sb.width / 2 - other.x), 'vertex snaps to the wall corner (x)').toBeLessThan(1.5);
  expect(Math.abs(sb.y + sb.height / 2 - other.y), 'vertex snaps to the wall corner (y)').toBeLessThan(1.5);
  await page.mouse.up();
  await expect(readout).not.toHaveText('7,13 m² · 12,18 m · lentelėje 6,90 m²');
  await page.keyboard.press('z');
  await expect(readout).toHaveText('7,13 m² · 12,18 m · lentelėje 6,90 m²');
  await page.keyboard.press('Escape');
  await expect(readout).toHaveCount(0);
  note('vertex snapped to a wall corner → Z → 7,13 m² again');

  // „Padalyti": a chord across 02 → parts measured → cancelled
  await focusRoom(page, '02');
  await page.getByTestId('outline-tool-split').click();
  const panel = page.getByTestId('outline-tool-panel');
  for (const p of await sheetPoints(page, 1, [[0.39086, 0.32], [0.4564, 0.32]])) await clickAt(page, p);
  await expect(panel).toContainText('Spustelėkite dalį, kuri lieka patalpai 02');
  await clickAt(page, (await sheetPoints(page, 1, [[0.42, 0.28]]))[0]);
  await expect(panel).toContainText('Lieka 02: 3,69 m² · lentelėje 6,90 m²');
  await expect(panel).toContainText('Kita dalis (3,44 m²)');
  await panel.getByRole('button', { name: 'Atšaukti' }).click();
  await expect(panel).toHaveCount(0);
  expect(outlineWrites, 'vertex edit and split were cancelled — nothing saved').toBe(0);
  note('split 02 → 3,69 + 3,44 m² (atšaukta)');

  // „Sujungti" 04 → 05 (saved): both printed areas billed, ceiling unchanged, finishes warning before and after
  await mergeRooms(page, project);
  await expect(roomRow(page, '04').getByTestId('room-merge-badge')).toHaveText('+ 05');
  await expect(roomRow(page, '04').getByTestId('room-merge-badge')).toHaveAttribute('title', /Patalpų apdaila skiriasi/);
  await expect(roomRow(page, '04')).toContainText('61,81');
  await expect(roomRow(page, '05').getByTestId('room-merge-badge')).toHaveText('sujungta į 04');
  await expectKiekiai(page, [['Dažymo kampų montavimas', '489,76 m'], ['Lubų glaistymas/dažymas', '143,27 m²']]);
  note('merge: 04 = 26,31 + 35,50 = 61,81 m² · lubos 143,27 · kampai 475,66 → 489,76');
  // W1-F F1 (was recorded as a bug by W0-A): the totals outside the billed lines count 05's 35,50 m² once —
  // inside 04 — so the room list's header stays 143,27 m² (not 178,77) and the server's floor-ratio checks
  // say what they said before the merge (no false „Lubų plotas 0,80× grindų ploto", no „…sienų plotas 1,72×").
  await expect(page.getByRole('button', { name: /^Patalpos 11 143,27 m²$/ })).toBeVisible();
  const floorRatios = (p) => (p.lt_sanity?.warnings || []).map((w) => w.message || '').filter((m) => /grindų ploto$/.test(m));
  await expect.poll(async () => floorRatios(await getProject()), { timeout: 30_000 }).toEqual(floorRatios(project));
  note(`after merge: „Patalpos 11 143,27 m²" · checks as before the merge: ${floorRatios(project).join(' · ') || '—'}`);
  // W1-F F2: 04 keeps the floor covering the floor plan gives it (it went to „—" and Patikra asked again)
  expect(roomsByNr(await getProject())['04']).toMatchObject({ grindu_danga: 'plyteles', grindu_danga_saltinis: 'grindu_planas' });
  const { questions } = await api(`/api/projects/${PROJECT}/questions`);
  const floorAsked = questions.filter((q) => q.kind === 'grindys').flatMap((q) => q.items.map((i) => i.room_nr));
  expect(floorAsked, 'Patikra does not ask 04\'s floor again').not.toContain('04');
  note(`04 grindys: plytelės (iš grindų plano) · Patikra klausia grindų: ${floorAsked.join(', ') || '—'}`);

  // „Atimti" (saved): a 2,06 m² column, „Kas atimama?" = kolona → 4 corners × 2,82 m
  await subtractColumn(page, await getProject());
  await expectKiekiai(page, [['Dažymo kampų montavimas', '501,04 m'], ['Lubų glaistymas/dažymas', '143,27 m²']]);
  note('subtract 2,06 m² kolona: kampai 489,76 → 501,04 · lubos 143,27');
  await shot(page, '05-room-tools');
  // W1-F F1: „Patalpų suvestinė" (Sąmata) adds the rooms the same way — 05 inside 04, once
  await page.getByTestId('step-samata').click();
  await page.getByTestId('samata-expand').click();
  await expect(page.getByRole('button', { name: /^Patalpų suvestinė/ })).toContainText('11 patalpų · 143,27 m²');
  note('Sąmata „Patalpų suvestinė": 11 patalpų · 143,27 m²');
});

test('6 measure tools snap to walls; lasso batch delete; Istorija undo', async ({ page }) => {
  await openProject(page);
  const pg1 = page.locator('div[data-page-number="1"]');
  const measureTexts = () => pg1.locator('svg text').evaluateAll((els) => els.map((e) => e.textContent));

  await loadGeometry(page, 1);
  await page.getByRole('button', { name: 'Atstumas', exact: true }).click();
  const pts = await sheetPoints(page, 1, ROOM_02);
  // hovering 3 px off a wall corner shows the orange corner marker exactly on the corner
  await page.mouse.move(pts[3].x + 3, pts[3].y - 3, { steps: 5 });
  const marker = pg1.locator(CORNER_MARK);
  await expect(marker).toHaveCount(1);
  const mb = await marker.boundingBox();
  expect(Math.abs(mb.x + mb.width / 2 - pts[3].x)).toBeLessThan(1.5);
  expect(Math.abs(mb.y + mb.height / 2 - pts[3].y)).toBeLessThan(1.5);
  await clickAt(page, { x: pts[3].x + 2, y: pts[3].y - 2 });
  // v3 W1-B: a distance is written on its second click — no „Baigti"
  await clickAt(page, { x: pts[2].x + 2, y: pts[2].y - 2 });
  await expect(toast(page, 'Atstumas: 1,58 m')).toBeVisible();

  await page.getByRole('button', { name: 'Plotas', exact: true }).click();
  for (const p of pts) await clickAt(page, { x: p.x + 2, y: p.y - 2 });
  await page.getByRole('button', { name: /Baigti/ }).click();
  await expect(toast(page, 'Plotas: 7,13 m²')).toBeVisible();

  await page.getByRole('button', { name: 'Perimetras', exact: true }).click();
  for (const p of pts) await clickAt(page, { x: p.x + 2, y: p.y - 2 });
  await page.getByRole('button', { name: /Baigti/ }).click();
  await expect(toast(page, 'Perimetras: 7,67 m')).toBeVisible();
  expect(await measureTexts()).toEqual(expect.arrayContaining(['1,58 m', '7,13 m²', '7,67 m']));
  note('snap to corner · Atstumas 1,58 m · Plotas 7,13 m² · Perimetras 7,67 m');

  await page.getByRole('button', { name: 'Kiekis', exact: true }).click();
  await page.getByTestId('clegend-add-type').click();
  await page.getByTestId('clegend-new-type-input').fill('Rozetės');
  await page.getByTestId('clegend-new-type-input').press('Enter');
  for (const p of await sheetPoints(page, 1, [[0.42, 0.30], [0.43, 0.34]])) await clickAt(page, p);
  await expect(page.getByTestId('count-legend-panel')).toContainText(/Rozetės\s*2/);
  await expect(pg1.locator('[data-ai-mark]'), 'hand-placed marks are not drawn hollow').toHaveCount(0);
  await expect(measRow(page, 'Rozetės', '2 vnt.')).toBeVisible();
  // saved: 3 measurements + 2 count marks, 1 count type
  await expect.poll(async () => fingerprint(await getProject()), { timeout: 15_000 }).toMatchObject({ countTypes: 1, measurements: 5 });
  note('Kiekis Rozetės 2 · saved 3 measurements + 2 marks');
  await page.keyboard.press('Escape');

  // Laso (L): a real loop around the marks → right-click → batch delete → Istorija → undo
  await page.evaluate(() => document.activeElement?.blur?.());
  await page.keyboard.press('l');
  await expect(page.getByRole('button', { name: 'Laso' })).toHaveAttribute('aria-pressed', 'true');
  const loop = await sheetPoints(page, 1, [[0.375, 0.235], [0.475, 0.235], [0.475, 0.395], [0.375, 0.395], [0.375, 0.24]]);
  await page.mouse.move(loop[0].x, loop[0].y, { steps: 3 });
  await page.mouse.down();
  for (const p of loop.slice(1)) await page.mouse.move(p.x, p.y, { steps: 12 });
  await page.mouse.up();
  const [inside] = await sheetPoints(page, 1, [[0.42, 0.32]]);
  await page.mouse.click(inside.x, inside.y, { button: 'right' });
  const menu = page.getByRole('menu');
  await expect(menu).toContainText('Pažymėta: 3 matavimai, 2 žymės');
  await menu.getByRole('menuitem', { name: 'Ištrinti visus (5)' }).click();
  await expect(measRow(page, 'Rozetės', '2 vnt.')).toHaveCount(0);
  await page.keyboard.press('Escape');
  await moreItem(page, 'viewer-history-toggle');
  const hist = page.getByTestId('history-panel');
  await expect(hist).toContainText('Pašalinti 5 matavimai');
  await hist.getByRole('button', { name: 'Atšaukti', exact: true }).click();
  await expect(hist).toContainText('atšaukta');
  await expect(measRow(page, 'Rozetės', '2 vnt.')).toBeVisible();
  expect(await measureTexts()).toEqual(expect.arrayContaining(['1,58 m', '7,13 m²', '7,67 m']));
  await shot(page, '06-measure-lasso-history');
  // v3 W1-B (audit F3): Esc closes Istorija too; its ✕ still does
  await page.keyboard.press('Escape');
  await expect(hist, 'Esc closes Istorija').toHaveCount(0);
  await moreItem(page, 'viewer-history-toggle');
  await page.getByTestId('history-panel').getByRole('button', { name: 'Uždaryti istoriją' }).click();
  await expect(page.getByTestId('history-panel')).toHaveCount(0);
  note('lasso 3 matavimai + 2 žymės → ištrinta 5 → Istorija atšaukė');
});

test('7 Rasti panašius → count with automatically-found marks', async ({ page }) => {
  await openProject(page);
  await page.getByTestId('sheet-rail').locator('li[data-sheet-page="3"] button').click();
  await page.getByTestId('viewer-symbol-search').click();
  const project = await getProject();
  const W = 595; const H = 842; // the sheet in points (A4, display frame) — checked below
  expect(roomsByNr(project)['01']._vieta).toMatchObject({ W, H });
  const half = [LAMP_HALF_PT / W, LAMP_HALF_PT / H];
  const [a, b] = await sheetPoints(page, 3, [[LAMP_3[0] - half[0], LAMP_3[1] - half[1]], [LAMP_3[0] + half[0], LAMP_3[1] + half[1]]]);
  const found = page.waitForResponse((r) => r.url().includes('/api/cv/find-symbol') && r.request().method() === 'POST');
  await dragBetween(page, a, b);
  const body = await (await found).json();
  const scores = body.candidates.map((c) => c.score).sort((x, y) => y - x);
  const panel = page.getByTestId('symbol-review-panel');
  await expect(panel.getByTestId('symbol-count-label')).toContainText(`rasta ${body.candidates.length}`);
  await panel.getByTestId('symbol-threshold').fill(String(LAMP_THRESHOLD));
  const atThreshold = scores.filter((s) => s >= LAMP_THRESHOLD).length;
  note(`find-symbol: ${body.candidates.length} candidates, top ${scores.slice(0, 4).join(' / ')}, ≥ 0,98 → ${atThreshold}`);
  await expect(panel.getByTestId('symbol-count-label')).toHaveText(`rasta ${body.candidates.length}, rodoma ${atThreshold} nuo 0,98`);
  await expect(panel.getByTestId('symbol-row')).toHaveCount(atThreshold);
  await expect(panel.getByTestId('symbol-row').first()).toContainText('pavyzdys');
  expect(atThreshold).toBe(2);
  await panel.getByTestId('symbol-type').selectOption('__new');
  await panel.getByTestId('symbol-new-type').fill('Pakabinami šviestuvai');
  await expect(panel.getByTestId('symbol-add')).toHaveText('Pridėti kaip kiekį (2 vnt.)');
  await panel.getByTestId('symbol-add').click();
  await expect(measRow(page, 'Pakabinami šviestuvai', '2 vnt.')).toBeVisible();
  await page.getByRole('button', { name: 'Kiekis', exact: true }).click();
  const legend = page.getByTestId('count-legend-panel');
  await expect(legend).toContainText('Pakabinami šviestuvai');
  await expect(legend).toContainText('2 rasta automatiškai');
  await expect(page.locator('div[data-page-number="3"] [data-ai-mark]'), 'found marks are drawn hollow').toHaveCount(2);
  await expect(page.getByTestId('clegend-ai-note')).toContainText('Tuščiavidurė žymė — rasta automatiškai, patikrinkite; pilna — pažymėta ranka.');
  await expect.poll(async () => fingerprint(await getProject()).countTypes, { timeout: 15_000 }).toBe(1);
  note('2 added as a count · legend „2 rasta automatiškai" (hollow marks)');
  await shot(page, '07-find-similar');
});

test('8 right panel tabs: Patalpos ir eilutės, Kiekiai, Pokalbis (no message sent)', async ({ page }) => {
  let chatCalls = 0;
  page.on('request', (r) => { if (r.url().includes('/chat-project')) chatCalls += 1; });
  await openProject(page);
  await expect(page.getByTestId('right-tab-patalpos')).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('button', { name: /^Patalpos 11 143,27 m²$/ })).toBeVisible();
  await expect(page.locator('[title^="Atidaryti psl."]')).toHaveCount(11);

  await page.getByTestId('right-tab-kiekiai').click();
  const tree = page.getByRole('tree', { name: 'Kiekiai pagal darbus ir patalpas' });
  await expect(tree.getByRole('button', { name: 'Sienų glaistymas dažymas 7' })).toBeVisible();
  await expect(tree.getByRole('button', { name: 'Lubų glaistymas dažymas 2' })).toBeVisible();
  const lubos = page.getByRole('treeitem', { name: /Lubų glaistymas\/dažymas 143,27 m²$/ });
  await expect(page.getByRole('treeitem', { name: /Dažymo kampų montavimas 475,66 m$/ })).toBeVisible();
  await lubos.click();
  await expect(lubos).toHaveAttribute('aria-expanded', 'true');
  const roomsOfLubos = page.getByRole('treeitem', { name: /^\d\d .* \d+,\d\d m²\d+ %/ });
  await expect(roomsOfLubos).toHaveCount(11);
  const areas = (await roomsOfLubos.allInnerTexts()).map((t) => Number(/([\d ]+,\d\d) m²/.exec(t)[1].replace(/\s/g, '').replace(',', '.')));
  expect(Math.round(areas.reduce((s, x) => s + x, 0) * 100) / 100).toBe(143.27);
  note(`Kiekiai: lubos 143,27 = Σ ${areas.length} rooms · kampai 475,66`);
  // click a room under the row ↔ that room is focused on the drawing (its room tools appear)
  await expect(page.getByTestId('outline-edit-start')).toHaveCount(0);
  await page.getByRole('treeitem', { name: /^03 Koridorius/ }).click();
  await expect(page.getByTestId('outline-edit-start')).toBeVisible();
  // eye toggle on a room under the row
  const eye = roomsOfLubos.first().getByRole('button', { name: 'Slėpti kontūrą' });
  await eye.click();
  await expect(roomsOfLubos.first().getByRole('button', { name: 'Rodyti kontūrą' })).toBeVisible();
  await roomsOfLubos.first().getByRole('button', { name: 'Rodyti kontūrą' }).click();
  // right-click → the row's menu → ask the chat about it (opens „Pokalbis", sends nothing)
  await lubos.click({ button: 'right' });
  const menu = page.getByRole('menu');
  for (const item of ['Rodyti brėžinyje tik šias patalpas', 'Atidaryti patikrą', 'Perskaičiuoti', 'Klausti pokalbyje apie šią eilutę']) {
    await expect(menu.getByRole('menuitem', { name: item })).toBeVisible();
  }
  await menu.getByRole('menuitem', { name: 'Klausti pokalbyje apie šią eilutę' }).click();
  await expect(page.getByTestId('right-tab-pokalbis')).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByText('Atsakymai pagal programos perskaitytus duomenis, ne iš brėžinio tiesiogiai.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Eilutė: Lubų glaistymas/dažymas' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Klausimas apie projektą' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Siųsti klausimą' })).toBeDisabled();
  await shot(page, '08-right-panel');
  expect(chatCalls, 'no chat message is sent (it would be a paid call)').toBe(0);
  note('Pokalbis: pill „Eilutė: Lubų glaistymas/dažymas", 0 messages sent');
});

test('9 Palyginti leidimus: a later edition laid over, matched by walls, no quantity changes', async ({ page }, info) => {
  await openProject(page);
  const before = fingerprint(await getProject());
  // a synthetic second edition: sheet 1 shifted 25 / 15 pt plus one added bar (make_revision.py)
  const pdfRes = await page.request.get(`/api/projects/${PROJECT}/pdf`);
  expect(pdfRes.ok()).toBe(true);
  const src = info.outputPath('drawing.pdf');
  const out = info.outputPath('leidimas-2.pdf');
  fs.mkdirSync(path.dirname(src), { recursive: true });
  fs.writeFileSync(src, await pdfRes.body());
  const commonDir = execFileSync('git', ['rev-parse', '--path-format=absolute', '--git-common-dir'], { cwd: REPO, encoding: 'utf8' }).trim();
  const python = process.env.E2E_PYTHON || [path.join(REPO, 'venv/bin/python'), path.join(path.dirname(commonDir), 'venv/bin/python')].find((p) => fs.existsSync(p));
  expect(python, 'the repo venv (with pikepdf) builds the synthetic edition — set E2E_PYTHON if it lives elsewhere').toBeTruthy();
  execFileSync(python, ['-I', PYTHON_HELPER, src, out]);

  await page.getByTestId('revision-compare-button').click();
  const panel = page.getByTestId('revision-compare-panel');
  await expect(panel).toContainText('Naujų leidimų dar nėra.');
  await panel.getByTestId('revision-file-input').setInputFiles(out);
  await expect(toast(page, 'Naujas leidimas įkeltas ir uždėtas ant brėžinio.')).toBeVisible({ timeout: 120_000 });
  await expect(panel).toContainText('leidimas-2.pdf');
  await expect(panel).toContainText('8 lap.');
  await expect(panel.getByRole('radio', { name: 'Skirtumai' })).toHaveAttribute('aria-checked', 'true');
  await expect(panel).toContainText('nauja — yra tik naujame leidime');
  await expect(panel).toContainText('išbraukta — buvo tik dabartiniame');
  await expect(panel.getByRole('slider')).toHaveCount(1);
  await expect(panel).toContainText(/Ant šio lapo — naujo leidimo lapas \d, sulygiuotas pagal sienas \(sutapimas \d,\d\d\)\./);

  const { leidimai } = await api(`/api/projects/${PROJECT}/pdf-revisions`);
  expect(leidimai).toHaveLength(1);
  const lapai = leidimai[0].lapai;
  expect(lapai['1']).toMatchObject({ old_page: 1, dx: -25, dy: 15, budas: 'sienos' });
  expect(lapai['1'].sutapimas).toBeGreaterThan(0.9);
  for (const n of ['2', '3', '4', '5', '6', '7', '8']) expect(lapai[n]).toMatchObject({ old_page: Number(n), dx: 0, dy: 0, budas: 'sienos' });
  note('8 / 8 sheets matched by walls · sheet 1 dx −25 dy 15');

  // the server's „Skirtumas" pictures: sheet 1 has new (evergreen) and removed (clay) lines, sheet 2 none
  const rid = leidimai[0].id;
  const colours = await page.evaluate(async ({ rid: r, project }) => {
    const count = async (n) => {
      const res = await fetch(`/api/projects/${project}/pdf-revisions/${r}/overlay/${n}?mode=skirtumas&dpi=72`);
      const bmp = await createImageBitmap(await res.blob());
      const c = new OffscreenCanvas(bmp.width, bmp.height);
      const g = c.getContext('2d');
      g.drawImage(bmp, 0, 0);
      const px = g.getImageData(0, 0, bmp.width, bmp.height).data;
      let nauja = 0; let isbraukta = 0;
      for (let i = 0; i < px.length; i += 4) {
        if (px[i + 3] < 128) continue;
        if (Math.abs(px[i] - 62) < 12 && Math.abs(px[i + 1] - 101) < 12 && Math.abs(px[i + 2] - 91) < 12) nauja += 1;
        else if (Math.abs(px[i] - 169) < 12 && Math.abs(px[i + 1] - 94) < 12 && Math.abs(px[i + 2] - 76) < 12) isbraukta += 1;
      }
      return { nauja, isbraukta };
    };
    return { 1: await count(1), 2: await count(2) };
  }, { rid, project: PROJECT });
  expect(colours[1].nauja).toBeGreaterThan(100);
  expect(colours[1].isbraukta).toBeGreaterThan(100);
  expect(colours[2]).toEqual({ nauja: 0, isbraukta: 0 });
  note(`skirtumas sheet 1: ${colours[1].nauja} new / ${colours[1].isbraukta} removed px · sheet 2: 0 / 0`);
  await expect(page.locator(`img[src*="/pdf-revisions/${rid}/overlay/1?mode=skirtumas"]`)).toHaveCount(1);
  await panel.getByRole('radio', { name: 'Naujas leidimas' }).click();
  await expect(page.locator(`img[src*="/pdf-revisions/${rid}/overlay/1?mode=naujas"]`)).toHaveCount(1);
  await shot(page, '09-revision-overlay');
  await panel.getByRole('button', { name: 'Išjungti (Esc)' }).click();
  await expect(page.getByTestId('revision-compare-button')).toHaveAttribute('aria-pressed', 'false');

  const after = fingerprint(await getProject());
  expect({ a04: after.a04, kampai: after.kampai, lubos: after.lubos, merged05: after.merged05 })
    .toEqual({ a04: before.a04, kampai: before.kampai, lubos: before.lubos, merged05: before.merged05 });
  note('no quantity changed (kampai 475,66, lubos 143,27)');
});

test('10 after 04 + 05: Patikra partition walls 5 → 3, kampai −5,64 m, one journal row', async ({ page }) => {
  await openProject(page);
  await loadGeometry(page, 1);
  await mergeRooms(page, await getProject());
  await subtractColumn(page, await getProject());
  await page.goto(`/project/${PROJECT}/patikra?kambarys=04`);
  await expect(page.getByRole('heading', { level: 1, name: /^04 / })).toBeVisible({ timeout: 60_000 });
  // W1-F F2: the merged 04 still says what the floor plan draws in it — not „dvi dangos", not a question
  await expect(page.getByText(/^Grindų plane \(7 psl\.\) ši patalpa nubraižyta tuo pačiu raštu/)).toBeVisible();
  await expect(page.getByText(/parašytos dvi dangos/)).toHaveCount(0);
  const learnedBefore = await learnedCount(page);
  const fact = page.locator('div')
    .filter({ has: page.getByRole('img', { name: /^Pertvarų sienos atviroje erdvėje/ }) })
    .filter({ has: page.getByRole('textbox', { name: 'Pertvarų sienų, vnt.' }) })
    .last();
  await expect(fact).toContainText('5 vnt.');
  await expect(fact).toContainText('2 + 3 = 5 — patalpos sujungtos.');
  const box = page.getByRole('textbox', { name: 'Pertvarų sienų, vnt.' });
  await expect(box).toHaveValue('5');
  await box.fill('3');
  await box.press('Enter');
  await expect(page.locator('p').filter({ hasText: /^Pertvarų sienos atviroje erdvėje\s*jūsų$/ })).toBeVisible();
  await expect(page.locator('p').filter({ hasText: /^3 vnt\.$/ })).toBeVisible();
  await expect(page.getByText('Pertvarų sienų skaičių įrašėte patys: 3.')).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'Sąmatoje pasikeitė' })).toContainText(/Dažymo kampų montavimas:\s*501,04 m\s*→\s*495,40 m/);
  await expect.poll(async () => fingerprint(await getProject()).kampai, { timeout: 15_000 }).toBe(495.4);
  await expect.poll(() => learnedCount(page), { timeout: 15_000 }).toBe(learnedBefore + 1);
  await page.getByTestId('learning-count').click();
  const journal = page.getByTestId('learning-journal');
  await expect(journal).toBeVisible();
  await expect(page.getByTestId('learning-csv')).toBeVisible();
  note(`2 + 3 = 5 → 3 jūsų · kampai 501,04 → 495,40 (−5,64) · Įsiminta ${learnedBefore} → ${learnedBefore + 1}`);
  await shot(page, '10-patikra-partitions');
});

/** demo-objektas_h as this browser's cache holds it (the write-through copy in localStorage). */
async function cachedProject(page) {
  return page.evaluate((id) => {
    try { return (JSON.parse(localStorage.getItem('samatu_projects') || '[]')).find((p) => p?.id === id) || {}; } catch { return {}; }
  }, PROJECT);
}

/**
 * W1-F F4: merge 04 + 05 in this browser, restore the start version ELSEWHERE (the Versijos route, as another
 * tab or device would), reload: the screen shows the server's copy, never this browser's newer cached one.
 */
async function restoredElsewhereThenReload(page) {
  await openProject(page);
  await loadGeometry(page, 1);
  await mergeRooms(page, await getProject());
  await expect.poll(async () => roomsByNr(await cachedProject(page))['05']?._sujungta_i || null, { timeout: 15_000 }).toBe('04');
  const start = readJson(START_JSON);
  // The server stamps a save to the SECOND: a restore in the same second as this browser's save would carry
  // the very stamp this browser last saw. Another tab or device takes longer than that.
  const saved = (await getProject()).updated_at;
  await expect.poll(() => new Date().toISOString().slice(0, 19) + 'Z', { timeout: 5_000 }).not.toBe(saved);
  await api(`/api/projects/${PROJECT}/versions/${start.version}/restore`, { method: 'POST' });
  expect(fingerprint(await getProject())).toMatchObject({ a04: 26.31, merged05: null, kampai: 475.66 });
  await page.reload();
  await viewerReady(page);
  await expect(roomRow(page, '04')).toContainText('26,31');
  await expect(roomRow(page, '05').getByTestId('room-merge-badge')).toHaveCount(0);
  await expect.poll(async () => roomsByNr(await cachedProject(page))['04']?.plotas_m2, { timeout: 15_000 }).toBe(26.31);
  await expect(page.getByTestId('server-refresh-notice')).toContainText('Atnaujinta iš serverio');
}

test('Versijos: a version restored elsewhere is what this browser shows after a reload', async ({ page }) => {
  await restoredElsewhereThenReload(page);
  note('merged here → restored elsewhere → reload: 04 26,31 · „Atnaujinta iš serverio"');
});

test('Versijos: … also when this browser\'s clock runs 10 min ahead of the server\'s', async ({ page }) => {
  // The cached copy carries the time of this browser's last edit, the server's copy the server's time: with the
  // PC clock 10 min fast the cached copy looked newer than the restore and stayed on screen (the stale sighting).
  await page.clock.install({ time: new Date(Date.now() + 10 * 60_000) });
  await restoredElsewhereThenReload(page);
  note('browser clock +10 min: merged here → restored elsewhere → reload: 04 26,31 · „Atnaujinta iš serverio"');
});

test('Top bar: Versijos — compare with current, restore keeps „Prieš grąžinant"', async ({ page }) => {
  await openProject(page);
  await loadGeometry(page, 1);
  await mergeRooms(page, await getProject());
  await page.getByRole('button', { name: 'Versijos', exact: true }).click();
  const drawer = page.getByRole('dialog', { name: 'Projekto versijos' });
  const items = drawer.getByRole('listitem');
  await expect(items.first()).toContainText('dabartinė');
  await expect(items.first().getByRole('button', { name: 'Grąžinti' })).toBeDisabled();
  const startInfo = readJson(START_JSON);
  const hhmm = new Date(startInfo.version_created_at).toLocaleTimeString('lt-LT', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Vilnius' });
  const kind = { issaugota: 'Išsaugota', perskaityta: 'Brėžinys perskaitytas iš naujo', lapas: 'Perskaitytas lapas', klausimas: 'Atsakytas klausimas', grazinta: 'Prieš grąžinant', kita: 'Kita' }[startInfo.version_saltinis] || 'Kita';
  const prev = items.filter({ hasText: new RegExp(`${hhmm}\\s*${escapeRe(kind)}`) }).first();
  await prev.getByRole('button', { name: 'Palyginti su dabartine' }).click();
  const diff = drawer.getByTestId('version-diff');
  await expect(diff).toContainText('Kas pasikeitė nuo šios versijos iki dabar (buvo → dabar):');
  await expect(diff).toContainText('Patalpa 04 Virtuvė/valgomasis: plotas 26,31 m² → 61,81 m²');
  await expect(diff).toContainText('Eilutė „Dažymo kampų montavimas“: kiekis 475,66 m → 489,76 m');
  note('diff: 04 26,31 → 61,81 m² · kampai 475,66 → 489,76');
  await prev.getByRole('button', { name: 'Grąžinti' }).click();
  const confirm = page.getByRole('alertdialog');
  await expect(confirm).toContainText('Grąžinti šią versiją?');
  await confirm.getByRole('button', { name: 'Grąžinti' }).click();
  await expect(toast(page, 'Grąžinta versija')).toBeVisible();
  await expect.poll(async () => fingerprint(await getProject()), { timeout: 30_000 }).toMatchObject({ a04: 26.31, merged05: null, kampai: 475.66 });
  await expect(items.filter({ hasText: 'Prieš grąžinant' }).first()).toBeVisible();
  const { versions } = await api(`/api/projects/${PROJECT}/versions`);
  expect(versions.some((v) => v.saltinis === 'grazinta' && /^Prieš grąžinant/.test(v.pavadinimas || ''))).toBe(true);
  await shot(page, '11-versijos');
  await drawer.getByRole('button', { name: 'Uždaryti versijas' }).click();
  await expect(roomRow(page, '04')).toContainText('26,31');
  await expect(roomRow(page, '04').getByTestId('room-merge-badge')).toHaveCount(0);
  note('restored → 04 26,31 · „Prieš grąžinant" kept');
});

test('Sąmata: Eksportuoti — Excel grouping preview and „PDF su žymėjimais" preview', async ({ page }) => {
  let downloads = 0;
  page.on('download', () => { downloads += 1; });
  await openProject(page);
  await page.getByTestId('step-samata').click();
  await page.getByRole('button', { name: 'Eksportuoti', exact: true }).click();
  for (const item of ['Excel (.xlsx)', 'PDF pasiūlymas', 'PDF su žymėjimais']) await expect(page.getByText(item, { exact: true })).toBeVisible();
  await page.getByText('Excel (.xlsx)', { exact: true }).click();
  await expect(page.getByText('Eksportuoti Excel — pasirinkti skyriai')).toBeVisible();
  const groups = page.getByRole('radiogroup', { name: 'Grupuoti pagal' });
  await expect(page.getByText('Stulpelis „Kodas“')).toBeVisible();
  // what the preview prints for each grouping on the start state: footer + first group heading
  const expected = {
    Skyrius: 'Rodoma 20 iš 106 eilučių · 11 grupių | Sienų glaistymas dažymas',
    Patalpas: 'Rodoma 20 iš 237 eilučių · 12 grupių | 01 Tambūras',
    'Darbų šeimas': 'Rodoma 20 iš 237 eilučių · 106 grupės | Sienų glaistymas dažymas · Sienų lyginimas Knauf Rotband',
    Lapus: 'Rodoma 20 iš 237 eilučių · 2 grupės | Lapas 1 — IŠDĖSTYMO PLANAS (su patalpų eksplikacija)',
    'Be grupavimo': 'Rodoma 20 iš 237 eilučių | —',
  };
  const got = {};
  let last = null;
  for (const name of Object.keys(expected)) {
    const preview = name === 'Skyrius' ? null : page.waitForResponse((r) => r.url().includes('/export-excel/preview') && r.ok());
    await groups.getByRole('radio', { name }).check();
    if (preview) await preview;
    const footer = page.getByText(/^Rodoma \d+ iš \d+ eilučių/);
    // the footer of THIS grouping (the previous one stays on screen until the new preview lands)
    await expect.poll(async () => {
      const t = (await footer.innerText()).split('.')[0].replace(/\s+/g, ' ').trim();
      return t !== last ? t : null;
    }, { timeout: 20_000 }).not.toBeNull();
    const foot = (await footer.innerText()).split('.')[0].replace(/\s+/g, ' ').trim();
    last = foot;
    const headings = page.locator('table tr.bg-muted td');
    const heading = (await headings.count()) ? (await headings.first().innerText()).trim() : '—';
    got[name] = `${foot} | ${heading}`;
  }
  const seen = Object.entries(got).map(([k, v]) => `${k}: ${v.split(' | ')[0].replace(/^Rodoma 20 iš /, '')}`);
  note(seen.join(' | '));
  expect(got).toEqual(expected);
  await shot(page, '12-export-excel-preview');
  await page.getByRole('button', { name: 'Atšaukti', exact: true }).click();

  await page.getByRole('button', { name: 'Eksportuoti', exact: true }).click();
  await page.getByText('PDF su žymėjimais', { exact: true }).click();
  const dlg = page.getByRole('dialog', { name: 'PDF su žymėjimais' });
  await expect(dlg).toBeVisible();
  const img = dlg.getByRole('img', { name: 'Pirmojo lapo su žymėjimais peržiūra' });
  await expect(img).toBeVisible({ timeout: 60_000 });
  expect(await img.evaluate((el) => el.naturalWidth)).toBeGreaterThan(100);
  await shot(page, '12-export-overlay-preview');
  await page.keyboard.press('Escape');
  expect(downloads, 'previews only — nothing downloaded').toBe(0);
  note('PDF su žymėjimais: sheet preview rendered, 0 downloads');
});
