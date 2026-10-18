import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildSheetRail, splitSheetName, disciplineOf, setSheetOverride, clearSheetOverride, overrideFor,
  searchHitsByPage, calloutHoverText, lapuForma, DISCIPLINES,
  floatingPanelLeft, SHEET_RAIL_WIDTH, THUMBNAIL_RAIL_WIDTH,
} from './sheetRail.js';

// The stored classification of the 8-sheet demo project (types and names as the blob carries them).
const H = [
  { nr: 1, tipas: 'floor_plan', pavadinimas: 'IŠDĖSTYMO PLANAS (su patalpų eksplikacija)' },
  { nr: 2, tipas: 'electrical', pavadinimas: 'ROZEČIŲ PLANAS' },
  { nr: 3, tipas: 'electrical', pavadinimas: 'APŠVIETIMO PLANAS' },
  { nr: 4, tipas: 'plumbing', pavadinimas: 'VANDENS ĮVADŲ PLANAS' },
  { nr: 5, tipas: 'ceiling_plan', pavadinimas: 'LUBŲ PLANAS' },
  { nr: 6, tipas: 'floor_plan', pavadinimas: 'SIENŲ DAŽYMO PLANAS' },
  { nr: 7, tipas: 'floor_plan', pavadinimas: 'GRINDŲ DANGŲ PLANAS' },
  { nr: 8, tipas: 'floor_plan', pavadinimas: 'PERTVARŲ PLANAS' },
];

test('groups follow the discipline order and leave empty groups out', () => {
  const { groups, sheets } = buildSheetRail({ puslapiai: H, pageCount: 8 });
  assert.equal(sheets.length, 8);
  assert.deepEqual(groups.map((g) => g.key), ['architektura', 'elektra', 'santechnika']);
  assert.deepEqual(groups[0].sheets.map((s) => s.page), [1, 5, 6, 7, 8]);
  assert.equal(groups[1].label, 'Elektra');
  assert.deepEqual(groups[1].sheets.map((s) => s.page), [2, 3]);
});

test('a dalis read from the title block beats the page type', () => {
  assert.equal(disciplineOf('floor_plan', 'E'), 'elektra');
  assert.equal(disciplineOf('floor_plan', 'unknown'), 'architektura');
  assert.equal(disciplineOf('specification'), 'kita');
  assert.equal(disciplineOf('unknown', null), 'kita');
  assert.equal(DISCIPLINES.at(-1).key, 'kita');
});

test('a coded name is split into its number and title', () => {
  assert.deepEqual(splitSheetName('IN.1A.-B.01 1A. BALDŲ PLANAS M 1:50'),
    { number: 'IN.1A.-B.01', shortNumber: 'B.01', title: '1A. BALDŲ PLANAS M 1:50' });
  assert.deepEqual(splitSheetName('LUBŲ PLANAS'), { number: null, shortNumber: null, title: 'LUBŲ PLANAS' });
  assert.deepEqual(splitSheetName('SA-02 Pjūvis'), { number: 'SA-02', shortNumber: 'SA-02', title: 'Pjūvis' });
});

test('pages the classification never saw still get a row', () => {
  const { sheets, groups } = buildSheetRail({ puslapiai: H.slice(0, 2), pageCount: 4 });
  assert.equal(sheets.length, 4);
  assert.equal(sheets[3].name, 'Lapas 4');
  assert.equal(sheets[3].classified, false);
  assert.equal(groups.at(-1).key, 'kita');
});

test('an override renames, retypes and regroups; the automatic values stay known', () => {
  const overrides = { 6: { name: 'Dažymas', type: 'wall_elevation' }, 2: { dalis: 'kita' } };
  const { sheets, groups } = buildSheetRail({ puslapiai: H, overrides, pageCount: 8 });
  const s6 = sheets[5];
  assert.equal(s6.name, 'Dažymas');
  assert.equal(s6.autoName, 'SIENŲ DAŽYMO PLANAS');
  assert.equal(s6.tipas, 'wall_elevation');
  assert.equal(s6.autoTipas, 'floor_plan');
  assert.equal(s6.overridden, true);
  assert.equal(sheets[1].discipline, 'kita');
  assert.deepEqual(groups.find((g) => g.key === 'kita').sheets.map((s) => s.page), [2]);
});

test('a user type moves the sheet to that type’s group unless a group was chosen too', () => {
  const { sheets } = buildSheetRail({ puslapiai: H, overrides: { 1: { type: 'electrical' } }, pageCount: 8 });
  assert.equal(sheets[0].discipline, 'elektra');
});

test('setSheetOverride stores only what differs from the automatic values', () => {
  const auto = { name: 'LUBŲ PLANAS', tipas: 'ceiling_plan', discipline: 'architektura' };
  let o = setSheetOverride({}, 5, { name: '  Lubos  ', type: 'ceiling_plan', dalis: 'architektura' }, auto);
  assert.deepEqual(o, { 5: { name: 'Lubos' } });
  o = setSheetOverride(o, 5, { name: 'LUBŲ PLANAS' }, auto);
  assert.deepEqual(o, {});
  o = setSheetOverride({}, 5, { type: 'nonsense', dalis: 'nowhere' }, auto);
  assert.deepEqual(o, {});
});

test('clearSheetOverride drops both key spellings and leaves the input untouched', () => {
  const before = { 5: { name: 'Lubos' }, 6: { name: 'X' } };
  const after = clearSheetOverride(before, 5);
  assert.deepEqual(after, { 6: { name: 'X' } });
  assert.deepEqual(before, { 5: { name: 'Lubos' }, 6: { name: 'X' } });
  assert.deepEqual(overrideFor({ 3: { name: 'a' } }, '3'), { name: 'a' });
  assert.equal(overrideFor(null, 3), null);
});

test('search results are counted per page', () => {
  assert.deepEqual(searchHitsByPage([{ pageIndex: 0 }, { pageIndex: 0 }, { pageIndex: 4 }, { pageIndex: -1 }, {}]), { 1: 2, 5: 1 });
  assert.deepEqual(searchHitsByPage(null), {});
});

test('the hover line names the target sheet as the rail shows it', () => {
  const { sheets } = buildSheetRail({ puslapiai: H, overrides: { 5: { name: 'Lubos' } }, pageCount: 8 });
  assert.equal(calloutHoverText({ target_page: 5, target_name: 'LUBŲ PLANAS' }, sheets), '→ lapas 5: Lubos');
  assert.equal(calloutHoverText({ target_page: 11, target_name: 'Išklotinės', other_pages: [12, 13] }, []),
    '→ lapas 11: Išklotinės (ir dar 2 lapai: 12, 13)');
});

test('Lithuanian plural of lapas', () => {
  assert.deepEqual([1, 2, 9, 10, 11, 12, 21, 22].map(lapuForma),
    ['lapas', 'lapai', 'lapai', 'lapų', 'lapų', 'lapų', 'lapas', 'lapai']);
});

test('legacy v8_pages rows name and type a sheet too', () => {
  const { sheets } = buildSheetRail({ puslapiai: [{ page: 1, type: 'ceiling_plan', label: 'Lubos' }], pageCount: 1 });
  assert.equal(sheets[0].name, 'Lubos');
  assert.equal(sheets[0].tipas, 'ceiling_plan');
});

// 2026-10-18 audit §4.6 item 4: „Rasti panašius" sat at left 156 while the sheet list is 232 px wide, so it
// covered ~76 px of the list; the count panel already used 240. One rule for every top-left panel now.
test('a floating panel starts right of whichever rail is open', () => {
  assert.equal(floatingPanelLeft({ railOpen: true, sheetRail: true }), 240);
  assert.equal(floatingPanelLeft({ railOpen: true, sheetRail: false }), 156);
  assert.equal(floatingPanelLeft({ railOpen: false, sheetRail: true }), 8);
  assert.ok(floatingPanelLeft({ railOpen: true, sheetRail: true }) > SHEET_RAIL_WIDTH);
  assert.ok(floatingPanelLeft({ railOpen: true, sheetRail: false }) > THUMBNAIL_RAIL_WIDTH);
});
