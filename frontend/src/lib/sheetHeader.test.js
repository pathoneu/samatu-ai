import test from 'node:test';
import assert from 'node:assert/strict';
import { sheetBadge, sheetHeaderModel } from './sheetHeader.js';
import { buildSheetRail } from './sheetRail.js';

const rail = buildSheetRail({
  puslapiai: [
    { nr: 1, tipas: 'floor_plan', pavadinimas: 'IN.1A.-B.01 Išdėstymo planas' },
    { nr: 2, tipas: 'ceiling_plan', pavadinimas: 'Lubų planas' },
  ],
  pageCount: 3,
});

test('the badge is the sheet number from its name, else the page number', () => {
  const m = sheetHeaderModel({ page: 1, total: 3, sheets: rail.sheets });
  assert.equal(m.badge, 'B.01');
  assert.equal(m.name, 'Išdėstymo planas');
  assert.equal(m.pager, '1 iš 3');
  assert.match(m.title, /^Lapas 1 iš 3: IN\.1A\.-B\.01 Išdėstymo planas$/);
  const two = sheetHeaderModel({ page: 2, total: 3, sheets: rail.sheets });
  assert.equal(two.badge, '2');
  assert.equal(two.name, 'Lubų planas');
});

test('an unnamed sheet reads „Lapas N" and the title does not repeat it', () => {
  const m = sheetHeaderModel({ page: 3, total: 3, sheets: rail.sheets });
  assert.equal(m.name, 'Lapas 3');
  assert.equal(m.title, 'Lapas 3 iš 3');
  const bare = sheetHeaderModel({ page: 2, total: 5 });
  assert.equal(bare.badge, '2');
  assert.equal(bare.name, 'Lapas 2');
});

test('the pager steps inside the set and says when an end is reached', () => {
  const first = sheetHeaderModel({ page: 1, total: 8 });
  assert.equal(first.canPrev, false);
  assert.equal(first.canNext, true);
  assert.equal(first.next, 2);
  const last = sheetHeaderModel({ page: 8, total: 8 });
  assert.equal(last.canNext, false);
  assert.equal(last.prev, 7);
  // out of range or missing → clamped, never NaN
  assert.equal(sheetHeaderModel({ page: 12, total: 8 }).page, 8);
  assert.equal(sheetHeaderModel({ page: null, total: null }).pager, '1 iš 1');
});

test('a long sheet number stays out of the chip', () => {
  assert.equal(sheetBadge({ shortNumber: 'ABCDEFGHIJ' }, 4), '4');
  assert.equal(sheetBadge(null, 4), '4');
});
