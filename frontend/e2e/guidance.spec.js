/**
 * Guidance and feedback (Pathon v3, track W5-C) on the demo project (demo-objektas_h).
 *
 *  - Patikra: Esc puts the focus on the current question in the list, Enter takes the proposed answer and the
 *    next question comes up; „Atšaukti pataisymą" takes it back (C4);
 *  - a room outlined without a table row (02, made table-less through the API) is asked „Ar tai katilinė?" —
 *    the word „BOILERIS" written inside its outline is the evidence; „Taip" names it, „Atšaukti" undoes (C3);
 *  - the room picker lists every room with its state in words and opens the one picked; a digit typed on a
 *    focused fact opens its number field with the digit in it (C7);
 *  - a sąmata row is deleted from its ⋯ menu, and the toast's „Atšaukti" puts it back (C8);
 *  - „Perskaityti lapą": the run is the bottom pill; a lost status call says „Ryšys nutrūko" with „Bandyti dar
 *    kartą", which picks the same run up and it finishes (C5).
 *
 * WRITES to the project — part of `npm run test:e2e`: every test starts from the guide's start state (the
 * suite's helpers restore it and prove it); the suite's teardown puts the pristine database back. €0: no
 * Vision call, no paid route (the run in the last test is the free lane).
 */
import { expect } from './pw.js';
import { PROJECT, api, getProject } from './state.js';
import { it, note, openProject, restoreStart, shot, toast } from './helpers.js';

const test = it;
test.describe.configure({ mode: 'default' });
test.beforeEach(async () => { await restoreStart(); });

const room = (p, nr) => (p.patalpos || []).find((r) => String(r.nr) === String(nr));

test('Patikra: Esc goes to the list, Enter takes the proposal and the next question comes up', async ({ page }) => {
  await openProject(page, { suffix: '/patikra' });
  const rail = page.locator('[data-question-rail] button');
  await expect(rail.first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId('question-keys')).toHaveText('Enter — tinka, kitas klausimas · Esc — atgal į sąrašą');
  // the first question whose proposal can be taken with one key
  const n = await rail.count();
  let picked = null;
  for (let i = 0; i < n; i += 1) {
    await rail.nth(i).click();
    const accept = page.locator('[data-testid^="question-card-"] [data-testid="question-accept"]').first();
    if (await accept.count() && await accept.isEnabled()) { picked = await rail.nth(i).getAttribute('data-testid'); break; }
  }
  expect(picked, 'a question with a proposal to take').toBeTruthy();
  const card = await page.locator('[data-testid^="question-card-"]').getAttribute('data-testid');
  await page.keyboard.press('Escape');
  await expect.poll(() => page.evaluate(() => document.activeElement?.getAttribute('data-testid'))).toBe(picked);
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('question-answered')).toBeVisible({ timeout: 30_000 });
  await expect.poll(async () => page.locator('[data-testid^="question-card-"], [data-testid="questions-done"]').first().getAttribute('data-testid'))
    .not.toBe(card);
  note(`Patikra: Enter answered ${card}`);
  await shot(page, 'w5c-patikra-enter');
  await page.getByTestId('question-answered').getByRole('button', { name: /Atšaukti/ }).click();
  await expect(page.getByTestId(picked)).toBeVisible();
});

test('a table-less room is asked its name from the words inside its outline — Taip, Atšaukti', async ({ page }) => {
  const p = await getProject();
  const { updated_at: _u, ...rest } = p;
  rest.patalpos = rest.patalpos.map((r) => (String(r.nr) === '02'
    ? { ...r, pavadinimas: 'Patalpa 02', plotas_saltinis: 'konturas', plotas_source: 'konturas', eksplikacija_row_idx: null }
    : r));
  await api(`/api/projects/${PROJECT}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(rest) });
  await openProject(page, { suffix: '/patikra?kambarys=02' });
  const chips = page.getByTestId('room-name-chips');
  await expect(chips).toContainText('Ar tai katilinė?', { timeout: 60_000 });
  await expect(chips).toContainText('Plane šioje patalpoje užrašyta: „BOILERIS“.');
  await shot(page, 'w5c-room-name-chips');
  await page.getByTestId('room-name-yes').click();
  await expect(page.getByTestId('room-name-saved')).toContainText('Patalpa pavadinta: Katilinė.');
  await expect.poll(async () => room(await getProject(), '02')?.pavadinimas, { timeout: 15_000 }).toBe('Katilinė');
  expect(room(await getProject(), '02').paskirtis).toBe('katiline');
  await page.getByTestId('room-name-saved').getByRole('button', { name: /Atšaukti/ }).click();
  await expect.poll(async () => room(await getProject(), '02')?.pavadinimas, { timeout: 15_000 }).toBe('Patalpa 02');
  await expect(chips).toBeVisible();
  note('room 02: „Ar tai katilinė?" (BOILERIS) → Katilinė → Atšaukti → Patalpa 02');
});

test('room picker: every room with its state in words; a digit typed on a focused fact opens its field', async ({ page }) => {
  await openProject(page, { suffix: '/patikra?kambarys=03' });
  await page.getByTestId('room-picker').click();
  const list = page.getByTestId('room-picker-list');
  await expect(list).toContainText('Liko patikrinti:');
  // the guide's start state: 05 is its own room (not merged) — each entry says its state in words
  await expect(page.getByTestId('room-picker-05')).toContainText(/patikrinta|liko patikrinti/);
  const states = await list.locator('[data-state-word]').evaluateAll((els) => els.map((e) => e.getAttribute('data-state-word')));
  expect(states).toHaveLength(11);
  expect(states.every((s) => ['checked', 'open', 'excluded', 'merged'].includes(s))).toBe(true);
  await shot(page, 'w5c-room-picker');
  await page.getByTestId('room-picker-09').click();
  await expect(page).toHaveURL(/kambarys=09/);
  const fact = page.getByTestId('fact-aukstis');
  await expect(fact).toBeVisible({ timeout: 30_000 });
  await fact.getByRole('button').first().focus();
  await page.keyboard.press('3');
  await expect(fact.locator('input').first()).toHaveValue('3');
  await page.keyboard.type(',05');
  await expect(fact.locator('input').first()).toHaveValue('3,05');
  await page.keyboard.press('Escape');
  note('picker: 11 rooms with states; digit → height field „3,05"');
});

test('sąmata: a row is deleted from its ⋯ menu and „Atšaukti" puts it back', async ({ page }) => {
  await openProject(page, { suffix: '?step=samata' });
  const menus = page.getByTestId('row-menu');
  await expect(menus.first()).toBeVisible({ timeout: 60_000 });
  // Fresh browser contexts can race with the frontend's initial write-through (projectStore debounces 400 ms,
  // and a 409 against a pre-flight save silently keeps the optimistic copy). Settle the network first and read
  // the baseline AFTER the page has loaded so delete lands on the server's actual version. 2026-10-29: alone
  // the test passed on this head, in-order it failed with „UI 116, server 117" — a stale base_updated_at. See
  // docs/.../2026-10-29-e2e-after-v4.md §3.
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => { /* dev builds rarely idle */ });
  const before = (await getProject()).darbu_sarasas.length;
  const shown = await menus.count();
  await menus.first().click();
  await page.getByTestId('row-menu-delete').click();
  await expect(menus).toHaveCount(shown - 1);
  await expect.poll(async () => (await getProject()).darbu_sarasas.length, { timeout: 15_000 }).toBe(before - 1);
  await toast(page, 'Eilutė ištrinta').getByRole('button', { name: 'Atšaukti' }).click();
  await expect(menus).toHaveCount(shown);
  await expect.poll(async () => (await getProject()).darbu_sarasas.length, { timeout: 15_000 }).toBe(before);
  note(`⋯ → Ištrinti → Atšaukti: ${before} rows → ${before - 1} → ${before}`);
});

test('run pill: a lost status call says so with „Bandyti dar kartą", which picks the same run up', async ({ page }) => {
  await openProject(page);
  let failed = 0;
  await page.route(/\/detect-run\/[^/?]+(\?|$)/, async (route) => {
    if (route.request().method() === 'GET' && failed === 0) { failed += 1; return route.abort('failed'); }
    return route.continue();
  });
  await page.getByTestId('detect-run-button').click();
  await page.getByTestId('detect-run-start-all').click();
  const pill = page.getByTestId('detect-run-progress');
  await expect(pill).toHaveAttribute('data-shape', 'pill');
  await expect(page.getByTestId('detect-run-lost')).toContainText('Ryšys nutrūko', { timeout: 30_000 });
  await shot(page, 'w5c-run-lost');
  await page.getByTestId('detect-run-retry').click();
  await expect(page.getByTestId('detect-run-lost')).toHaveCount(0);
  await expect(page.getByTestId('detect-run-headline')).toHaveText('Perskaityta · pritaikoma visam brėžiniui', { timeout: 120_000 });
  // the pill stands at the bottom of the drawing, clear of the top row of tool cards
  const box = await pill.boundingBox();
  const canvas = await page.getByTestId('viewer-root').boundingBox();
  expect(box.y + box.height).toBeGreaterThan(canvas.y + canvas.height - 120);
  await shot(page, 'w5c-run-pill-done');
  note('run pill: lost once → Bandyti dar kartą → finished');
});
