/**
 * Patikra answers every question on its card (Pathon v3 B1-C, 2026-10-19) on the demo project (demo-objektas_h).
 *
 * The founder on the first walk, at „Durys ir langai: patikrinkite 2 patalpas": „Čia kur patikra, negaliu iškart
 * vietoje pataisyti to, ką reikia. Negerai." The card now carries, per room to check, the list's number and the
 * walls' number and a field per kind pre-filled with the walls' number:
 *  - no „Atidaryti patalpą" anywhere on the card, and the page never changes;
 *  - Enter in a field = „Tinka": the room's doors are set, recomputed, what moved is shown above the next question;
 *  - „Atšaukti pataisymą" puts the doors back and the question returns.
 *
 * WRITES to the project — every test starts from the guide's start state (helpers restore and prove it); the
 * suite's teardown puts the pristine database back. €0: no Vision call, no paid route.
 */
import { expect } from './pw.js';
import { getProject } from './state.js';
import { it, note, openProject, restoreStart, shot } from './helpers.js';

const test = it;
test.describe.configure({ mode: 'default' });
test.beforeEach(async () => { await restoreStart(); });

const DOORS = new Set(['duris', 'pasleptos_duris']);
const room = (p, nr) => (p.patalpos || []).find((r) => String(r.nr) === String(nr));
const doorsOf = (r) => (r?.elementai || []).filter((e) => DOORS.has(e.tipas) && !e._praejimas)
  .reduce((s, e) => s + (e.kiekis === 0 ? 0 : Number(e.kiekis) || 1), 0);

test('doors and windows are answered on the card: the walls\' number, Enter, what moved, Atšaukti', async ({ page }) => {
  await openProject(page, { suffix: '/patikra' });
  const railItem = page.getByTestId('question-rail-angos');
  await expect(railItem).toBeVisible({ timeout: 60_000 });
  await railItem.click();
  const card = page.getByTestId('question-card-angos');
  await expect(card).toBeVisible();
  await expect(card).not.toContainText('Atidaryti patalpą');
  await expect(card).not.toContainText('vienu paspaudimu pataisyti negaliu');
  await expect(card).toContainText('siūlau tiek, kiek nubraižyta sienose');

  // the first room to check: its two numbers and the field opened on the walls' number
  const row = card.locator('[data-testid^="opening-manual-"]').first();
  const nr = (await row.getAttribute('data-testid')).replace('opening-manual-', '');
  const numbers = await card.getByTestId(`opening-numbers-${nr}-durys`).innerText();
  const m = /sąraše (\d+) · sienose (\d+)/.exec(numbers);
  expect(m, 'the list number and the walls number are shown').toBeTruthy();
  const [listed, walls] = [Number(m[1]), Number(m[2])];
  const field = card.getByTestId(`opening-count-${nr}-durys`);
  const proposed = Number(await field.inputValue());
  expect(proposed).toBe(walls > 0 || listed === 0 ? walls : 1);
  await expect(card.getByTestId(`opening-effect-${nr}-durys`)).not.toBeEmpty();
  await expect(card.getByTestId(`opening-show-${nr}`)).toBeVisible();
  note(`Patikra in place: room ${nr} doors listed ${listed}, in the walls ${walls}, proposed ${proposed}`);
  await shot(page, 'b1c-doors-card');

  const before = await getProject();
  const url = page.url();
  await field.focus();
  await field.press('Enter');
  await expect(page.getByTestId('question-answered')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('question-answered')).toContainText('durų ir langų skaičius įrašytas');
  expect(page.url(), 'no page change').toBe(url);
  // the next question comes up (or the done card)
  await expect.poll(async () => page.locator('[data-testid^="question-card-"], [data-testid="questions-done"]').first().getAttribute('data-testid'))
    .not.toBe('question-card-angos');
  await expect.poll(async () => doorsOf(room(await getProject(), nr)), { timeout: 20_000 }).toBe(proposed);
  const after = await getProject();
  expect(room(after, nr)._angos_patikrinta_at, 'the room is marked as answered').toBeTruthy();
  note(`Patikra in place: room ${nr} doors ${doorsOf(room(before, nr))} → ${doorsOf(room(after, nr))}`);
  await shot(page, 'b1c-doors-answered');

  await page.getByTestId('question-answered').getByRole('button', { name: /Atšaukti/ }).click();
  await expect(page.getByTestId('question-card-angos')).toBeVisible({ timeout: 30_000 });
  await expect.poll(async () => doorsOf(room(await getProject(), nr)), { timeout: 20_000 }).toBe(doorsOf(room(before, nr)));
  expect(room(await getProject(), nr)._angos_patikrinta_at ?? null).toBe(room(before, nr)._angos_patikrinta_at ?? null);
});
