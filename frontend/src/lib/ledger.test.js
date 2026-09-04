import test from 'node:test';
import assert from 'node:assert/strict';

import {
  contributionsOf, excludedOf, findRoom, hasLedger, isAreaRead, isHeightRead,
  anchorNote, findRowById, isManualRow, ledgerFallback, ltEur, ltNumber,
  ltQuantity, rollUpHeadline, rollUpIsAuthoritative, sortedContributions,
  sourceLabel, splitContributions, termEntries, termShare, unitLabel,
} from './ledger.js';

// The kampai line from the Objektas A demo blob, rebuilt through the real builder.
const KAMPAI = {
  id: '012ed8ac98ad',
  aprasymas: 'Dažymo kampų montavimas',
  mato_vnt: 'm',
  kiekis: 437.7,
  contributions: [
    {
      room_nr: '103', room_name: 'Koridorius', page: 2, value: 81.4, unit: 'm',
      included_because: 'Dažomos sienos — kampai armuojami', geometry: 'polygon',
      terms: {
        'vidiniai kampai': 11.2, 'angų atbrailos': 30.0,
        'pusiniai kampai': 25.2, 'perimetras': 15.0,
      },
    },
    {
      room_nr: '104', room_name: 'Darbo kambarys', page: 2, value: 38.8, unit: 'm',
      included_because: 'Dažomos sienos — kampai armuojami', geometry: 'marker',
    },
    {
      room_nr: '105', room_name: 'Garažas', page: 2, value: 30.5, unit: 'm',
      included_because: 'Dažomos sienos — kampai armuojami', geometry: 'polygon',
    },
  ],
  excluded: [
    { room_nr: '107', room_name: 'Vaikų san.mazgas',
      excluded_because: 'Visos sienos dengiamos plytelėmis' },
  ],
  roll_up: [{ op: 'sum', label: 'Σ 9 patalpų', value: 437.7 }],
};

const GRINDJUOSTES_ROLL_UP = [
  { op: 'sum', label: 'Σ 6 patalpų', value: 111.87 },
  { op: 'cap', label: 'Riba 0,65 m/m²', value: 107.67, note: 'Kiekvienos patalpos dalis…' },
];

test('ltNumber writes the LT decimal comma with fixed digits', () => {
  assert.equal(ltNumber(501.3), '501,30');
  assert.equal(ltNumber(0), '0,00');
  assert.equal(ltNumber(2.8, 2), '2,80');
  assert.equal(ltNumber(null), '—');
  assert.equal(ltNumber('abc'), '—');
});

test('unit labels use the typographic spelling the rest of the app writes', () => {
  assert.equal(unitLabel('m2'), 'm²');
  assert.equal(unitLabel('m3'), 'm³');
  assert.equal(unitLabel('m'), 'm');
  assert.equal(unitLabel('vnt.'), 'vnt.');
  assert.equal(unitLabel(null), '');
});

test('ltQuantity and ltEur format for display', () => {
  assert.equal(ltQuantity(437.7, 'm'), '437,70 m');
  assert.equal(ltQuantity(276.58, 'm2'), '276,58 m²');
  assert.equal(ltQuantity(3, ''), '3,00');
  // lt-LT groups thousands with a non-breaking space — keep it, the sąmata
  // exports already learned the hard way that a number must not wrap.
  assert.equal(ltEur(2648), '2 648 €');
  assert.equal(ltEur(null), '—');
});

test('hasLedger only accepts a populated roll_up', () => {
  assert.equal(hasLedger(KAMPAI), true);
  assert.equal(hasLedger({ roll_up: [] }), false);
  assert.equal(hasLedger({}), false);
  assert.equal(hasLedger(null), false);
});

test('a hand-added row is recognised by its rnk- id', () => {
  assert.equal(isManualRow({ id: 'rnk-abc123' }), true);
  assert.equal(isManualRow(KAMPAI), false);
  assert.equal(isManualRow({}), false);
});

test('the headline renders the server chain verbatim, never a re-sum', () => {
  assert.equal(rollUpHeadline(KAMPAI.roll_up, 'm'), 'Σ 9 patalpų 437,70 m');
  assert.equal(
    rollUpHeadline(GRINDJUOSTES_ROLL_UP, 'm'),
    'Σ 6 patalpų 111,87 m → Riba 0,65 m/m² 107,67 m');
  assert.equal(rollUpHeadline([], 'm'), null);
  assert.equal(rollUpHeadline(null, 'm'), null);
});

test('the headline shows the capped total, not the sum of the contributions', () => {
  // The whole point: 111,87 is what the rooms add up to, 107,67 is what is
  // billed. A client-side Σ would print the wrong one.
  const headline = rollUpHeadline(GRINDJUOSTES_ROLL_UP, 'm');
  assert.ok(headline.endsWith('107,67 m'));
});

test('contributions sort biggest-first without mutating the input', () => {
  const original = [...KAMPAI.contributions];
  const sorted = sortedContributions(KAMPAI.contributions);
  assert.deepEqual(sorted.map(c => c.room_nr), ['103', '104', '105']);
  assert.deepEqual(KAMPAI.contributions, original);
  assert.deepEqual(sortedContributions(null), []);
});

test('splitContributions collapses beyond the limit', () => {
  const many = Array.from({ length: 9 }, (_, i) => ({ room_nr: String(i), value: i }));
  const split = splitContributions(many, 5);
  assert.equal(split.shown.length, 5);
  assert.equal(split.hiddenCount, 4);
  assert.equal(split.total, 9);
  assert.deepEqual(split.shown.map(c => c.value), [8, 7, 6, 5, 4]);

  const small = splitContributions(KAMPAI.contributions, 5);
  assert.equal(small.hiddenCount, 0);
  assert.equal(small.shown.length, 3);
});

test('termEntries keeps the builder order and drops empty values', () => {
  const entries = termEntries({ a: 1.5, b: null, c: 0, d: undefined });
  assert.deepEqual(entries, [{ label: 'a', value: 1.5 }, { label: 'c', value: 0 }]);
  assert.deepEqual(termEntries(null), []);
});

test('termShare weighs the known drivers and abstains on unknown terms', () => {
  const kampai = KAMPAI.contributions[0].terms;
  // 11,2 + 25,2 of 81,4 lean on the ceiling height.
  assert.ok(Math.abs(termShare(kampai, 'height') - 36.4 / 81.4) < 1e-9);
  assert.ok(Math.abs(termShare(kampai, 'perimeter') - 15.0 / 81.4) < 1e-9);
  // No terms at all → no opinion, not zero.
  assert.equal(termShare(null, 'height'), null);
  assert.equal(termShare({}, 'height'), null);
  // Unknown vocabulary contributes to the denominator only.
  assert.equal(termShare({ 'nauja sąvoka': 5 }, 'height'), 0);
});

test('grindjuosčių terms lean on the perimeter, not the height', () => {
  const terms = { 'perimetras be durų': 15.09, 'atliekos 10 %': 1.51 };
  assert.equal(termShare(terms, 'height'), 0);
  assert.equal(termShare(terms, 'perimeter'), 1);
});

test('source tiers say which numbers were read and which were assumed', () => {
  assert.equal(isHeightRead('per_room'), true);
  assert.equal(isHeightRead('ceiling_plan_marker'), true);
  assert.equal(isHeightRead('section_average'), false);
  assert.equal(isHeightRead('default_fallback'), false);
  assert.equal(isHeightRead(null), false);

  assert.equal(isAreaRead('eksplikacija'), true);
  assert.equal(isAreaRead('polygon'), false);
  assert.equal(isAreaRead(undefined), false);
});

test('sourceLabel speaks Lithuanian and passes unknown keys through', () => {
  assert.equal(sourceLabel('eksplikacija'), 'patalpų eksplikacija brėžinyje');
  assert.equal(sourceLabel('simboliai_brezinyje'), 'brėžinyje suskaičiuoti simboliai');
  assert.equal(sourceLabel('naujas_saltinis'), 'naujas_saltinis');
  assert.equal(sourceLabel(''), null);
});

test('a row without a ledger still gets an honest explanation', () => {
  assert.deepEqual(ledgerFallback({ id: 'rnk-1' }), { kind: 'manual' });
  assert.deepEqual(
    ledgerFallback({ id: 'abc', saltinis: 'simboliai_brezinyje' }),
    { kind: 'unwired', source: 'brėžinyje suskaičiuoti simboliai' });
  assert.deepEqual(ledgerFallback({ id: 'abc' }), { kind: 'unwired', source: null });
});

test('contribution and exclusion readers tolerate old blobs', () => {
  assert.equal(contributionsOf(KAMPAI).length, 3);
  assert.deepEqual(contributionsOf({}), []);
  assert.equal(excludedOf(KAMPAI).length, 1);
  assert.deepEqual(excludedOf({ excluded: null }), []);
});

test('findRoom matches on string-vs-number room numbers', () => {
  const rooms = [{ nr: 103, pavadinimas: 'Koridorius' }, { nr: '110' }];
  assert.equal(findRoom(rooms, '103').pavadinimas, 'Koridorius');
  assert.equal(findRoom(rooms, 110).nr, '110');
  assert.equal(findRoom(rooms, '999'), null);
  assert.equal(findRoom(rooms, null), null);
  assert.equal(findRoom(null, '103'), null);
});

// The anchored ceiling: the eksplikacija's own „Iš viso" minus the rooms nobody
// paints. Its contributions are the drawing's per-room figures and their Σ is
// deliberately NOT the billed quantity.
const CEILING_ANCHORED = {
  id: 'ceil01',
  mato_vnt: 'm²',
  kiekis: 141.31,
  contributions: [
    { room_nr: '102', room_name: 'Svetainė', value: 50.5, unit: 'm2' },
    { room_nr: '110', room_name: 'Miegamasis', value: 23.97, unit: 'm2' },
  ],
  excluded: [],
  roll_up: [
    { op: 'anchor', label: 'Eksplikacijos „Iš viso"', value: 165.61,
      note: 'Patalpų lentelės suma iš brėžinio' },
    { op: 'sum', label: '− įtempiamos lubos', value: 141.31, note: 'Atimta 24,30 m²' },
  ],
};

test('a chain with an anchor is authoritative, a plain Σ is not', () => {
  assert.equal(rollUpIsAuthoritative(CEILING_ANCHORED.roll_up), true);
  assert.equal(rollUpIsAuthoritative(GRINDJUOSTES_ROLL_UP), true);   // cap
  assert.equal(rollUpIsAuthoritative(KAMPAI.roll_up), false);        // plain Σ
  assert.equal(rollUpIsAuthoritative([
    { op: 'sum', label: 'Σ 3 patalpų', value: 10 },
    { op: 'sum', label: 'Suapvalinta', value: 10.01 },
  ]), false);
  assert.equal(rollUpIsAuthoritative([]), false);
  assert.equal(rollUpIsAuthoritative(null), false);
});

test('the anchor step lends the panel its own explanation', () => {
  assert.equal(anchorNote(CEILING_ANCHORED.roll_up), 'Patalpų lentelės suma iš brėžinio');
  // No note written yet → the caller falls back to its own generic sentence.
  assert.equal(anchorNote([{ op: 'anchor', label: 'x', value: 1 }]), null);
  assert.equal(anchorNote(KAMPAI.roll_up), null);
  assert.equal(anchorNote(null), null);
});

test('the anchored ceiling is never presented as the sum of its rooms', () => {
  // 50,50 + 23,97 = 74,47, and the line bills 141,31. Nothing in the module
  // may produce that Σ, and the chain still ends on the billed number.
  const headline = rollUpHeadline(CEILING_ANCHORED.roll_up, CEILING_ANCHORED.mato_vnt);
  assert.ok(headline.endsWith('141,31 m²'));
  assert.ok(!headline.includes('74,47'));
});

test('findRowById refuses to resolve a duplicated id to the wrong row', () => {
  const rows = [
    { id: 'dup', aprasymas: 'Dažymo kampų montavimas', skyrius: 'A', kiekis: 1 },
    { id: 'dup', aprasymas: 'Grindjuosčių dažymas', skyrius: 'B', kiekis: 2 },
    { id: 'uniq', aprasymas: 'Vienintelė', skyrius: 'A', kiekis: 3 },
  ];
  // A unique id resolves.
  assert.equal(findRowById(rows, { id: 'uniq' }).kiekis, 3);
  // A duplicated id falls through to the label pair, which IS unique here.
  assert.equal(
    findRowById(rows, { id: 'dup', aprasymas: 'Grindjuosčių dažymas', skyrius: 'B' }).kiekis, 2);
  // Duplicated id AND no distinguishing label → no match at all, never a guess.
  assert.equal(findRowById(rows, { id: 'dup' }), null);
  // Old blobs with no id still match on the label pair.
  assert.equal(findRowById(rows, { aprasymas: 'Vienintelė', skyrius: 'A' }).kiekis, 3);
  // Two rows sharing a label as well → unresolvable.
  const twins = [
    { id: 'a', aprasymas: 'Nauja eilutė', skyrius: 'A' },
    { id: 'b', aprasymas: 'Nauja eilutė', skyrius: 'A' },
  ];
  assert.equal(findRowById(twins, { aprasymas: 'Nauja eilutė', skyrius: 'A' }), null);
  assert.equal(findRowById(null, { id: 'x' }), null);
  assert.equal(findRowById([], null), null);
});

test('rollUpIsAuthoritative: the builder-measured flag wins over the op heuristic', () => {
  const plainSum = [{ op: 'sum', label: 'Σ 3 patalpų', value: 30 }];
  // A plain Σ chain whose contributions the builder found NOT to add up (it
  // measured against kiekis) → authoritative chain, no Σ affordance.
  assert.equal(rollUpIsAuthoritative(plainSum, { contributions_sum_to_total: false }), true);
  // …and an anchored chain the builder measured as adding up → not authoritative.
  const anchored = [{ op: 'anchor', label: 'Iš lentelės', value: 100 }];
  assert.equal(rollUpIsAuthoritative(anchored, { contributions_sum_to_total: true }), false);
  // No flag (older blobs) → the heuristic as before.
  assert.equal(rollUpIsAuthoritative(anchored, {}), true);
  assert.equal(rollUpIsAuthoritative(plainSum, {}), false);
});
