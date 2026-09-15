import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  scorePair,
  bestMatchForPozicija,
  applyPriceListToPositions,
  manualPricePatch,
  findDefaultPriceList,
  autoFillFromDefaultPriceList,
  describeAmbiguous,
  AMBIGUOUS_ROWS_SHOWN,
} from './applyPriceList.js';

test('scorePair: exact match → 1.0', () => {
  assert.equal(scorePair('Sienų dažymas', 'sienų dažymas'), 1.0);
});

test('scorePair: substring → 0.92', () => {
  assert.equal(scorePair('Sienų dažymas', 'Sienų dažymas, 2 sluoksniai'), 0.92);
});

test('scorePair: Jaccard on shared tokens', () => {
  const s = scorePair('Sienų pirminis glaistymas Q1', 'Sienų antrinis glaistymas Q2');
  // Shared tokens: ['sienu', 'glaistymas']; the Q-levels count as tokens since
  // 2026-09-02 (they are the priced difference), so jaccard = 2/6 ≈ 0.33 and
  // the stemmed overlap (2026-09-15) 2/4 = 0.5. Either way this is well under
  // MIN_SCORE — different work, no fill.
  assert.ok(s >= 0.25 && s <= 0.55, `expected 0.33–0.5, got ${s}`);
  assert.ok(s < 0.78);
});

test('scorePair: empty inputs → 0', () => {
  assert.equal(scorePair('', 'whatever'), 0);
  assert.equal(scorePair('whatever', ''), 0);
});

test('bestMatchForPozicija: picks highest score', () => {
  const poz = { aprasymas: 'Sienų dažymas (1 sluoksnis)', vnt: 'm²' };
  const items = [
    { aprasymas: 'Lubų dažymas', vnt: 'm²', kaina: 8 },
    { aprasymas: 'Sienų dažymas, 1 sluoksnis', vnt: 'm²', kaina: 12 },
    { aprasymas: 'Grindjuosčių montavimas', vnt: 'm', kaina: 5 },
  ];
  const m = bestMatchForPozicija(poz, items);
  assert.ok(m);
  assert.equal(m.item.kaina, 12);
});

test('bestMatchForPozicija: rejects unit mismatch', () => {
  const poz = { aprasymas: 'Sienų dažymas', vnt: 'm²' };
  const items = [
    { aprasymas: 'Sienų dažymas', vnt: 'vnt', kaina: 12 },
  ];
  // Even though aprašymas is identical, vnt differs → no match
  assert.equal(bestMatchForPozicija(poz, items), null);
});

test('bestMatchForPozicija: returns null below threshold', () => {
  const poz = { aprasymas: 'Sienų dažymas', vnt: 'm²' };
  const items = [{ aprasymas: 'Visiškai kitas darbas', vnt: 'm²', kaina: 99 }];
  assert.equal(bestMatchForPozicija(poz, items), null);
});

test('applyPriceListToPositions: fills matched, leaves rest', () => {
  const poz = [
    { id: 1, aprasymas: 'Sienų dažymas', vnt: 'm²', kiekis: 100 },
    { id: 2, aprasymas: 'Specialus darbas niekur nerastas', vnt: 'kompl', kiekis: 1 },
  ];
  const priceList = [
    { aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 7.5 },
  ];
  const out = applyPriceListToPositions(poz, priceList);
  assert.equal(out.applied, 1);
  assert.equal(out.skipped, 1);
  assert.equal(out.items[0].kaina, 7.5);
  assert.equal(out.items[0].kaina_source, 'kainynas');
  assert.equal(out.items[1].kaina, undefined);
});

test('applyPriceListToPositions: respects manual overrides by default', () => {
  const poz = [
    { id: 1, aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 99, kaina_source: 'manual' },
  ];
  const priceList = [{ aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 7.5 }];
  const out = applyPriceListToPositions(poz, priceList);
  assert.equal(out.applied, 0);
  assert.equal(out.skipped, 1);
  assert.equal(out.items[0].kaina, 99);  // manual price preserved
});

test('applyPriceListToPositions: overwriteManual flag does override', () => {
  const poz = [
    { id: 1, aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 99, kaina_source: 'manual' },
  ];
  const priceList = [{ aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 7.5 }];
  const out = applyPriceListToPositions(poz, priceList, { overwriteManual: true });
  assert.equal(out.applied, 1);
  assert.equal(out.items[0].kaina, 7.5);
});

test('applyPriceListToPositions: empty inputs', () => {
  const out1 = applyPriceListToPositions([], [{ aprasymas: 'x', kaina: 1 }]);
  assert.equal(out1.applied, 0);
  assert.deepEqual(out1.items, []);

  const out2 = applyPriceListToPositions([{ aprasymas: 'x' }], []);
  assert.equal(out2.applied, 0);
  assert.equal(out2.skipped, 1);
});

// ── manualPricePatch — provenance stamping at the price editors ─────────────
// Mirrors how every commit site merges the patch into the row.
function commitPrice(row, typedKaina) {
  return {
    ...row,
    kaina: typedKaina,
    suma: (row.kiekis || 0) * typedKaina,
    ...manualPricePatch(row, typedKaina),
  };
}

test('manualPricePatch: typing a price into an empty row marks it manual', () => {
  const row = commitPrice({ aprasymas: 'Sienų dažymas', kiekis: 100, kaina: 0 }, 40);
  assert.equal(row.kaina, 40);
  assert.equal(row.kaina_source, 'manual');
});

test('manualPricePatch: editing a kainynas price flips source to manual and drops match score', () => {
  const applied = { aprasymas: 'Sienų dažymas', kiekis: 100, kaina: 7.5, kaina_source: 'kainynas', kaina_match_score: 0.92 };
  const row = commitPrice(applied, 9);
  assert.equal(row.kaina_source, 'manual');
  assert.equal(row.kaina_match_score, undefined);
});

test('manualPricePatch: committing an unchanged price leaves provenance alone', () => {
  const applied = { aprasymas: 'Sienų dažymas', kiekis: 100, kaina: 7.5, kaina_source: 'kainynas', kaina_match_score: 0.92 };
  // Row editor saved with only the description changed — price untouched.
  const row = commitPrice(applied, 7.5);
  assert.equal(row.kaina_source, 'kainynas');
  assert.equal(row.kaina_match_score, 0.92);
});

test('manualPricePatch: clearing to 0 resets source so kainynas may refill', () => {
  const manual = { aprasymas: 'Sienų dažymas', vnt: 'm²', kiekis: 100, kaina: 40, kaina_source: 'manual' };
  const cleared = commitPrice(manual, 0);
  assert.notEqual(cleared.kaina_source, 'manual');
  const out = applyPriceListToPositions([cleared], [{ aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 7.5 }]);
  assert.equal(out.items[0].kaina, 7.5);
  assert.equal(out.items[0].kaina_source, 'kainynas');
});

test('P0 flow: hand-typed price survives apply; kainynas rows update on re-apply', () => {
  const rows = [
    commitPrice({ aprasymas: 'Sienų dažymas', vnt: 'm²', kiekis: 100, kaina: 0 }, 40),
    { aprasymas: 'Lubų dažymas', vnt: 'm²', kiekis: 50 },
  ];
  const listV1 = [
    { aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 7.5 },
    { aprasymas: 'Lubų dažymas', vnt: 'm²', kaina: 6 },
  ];
  const first = applyPriceListToPositions(rows, listV1);
  assert.equal(first.items[0].kaina, 40);          // the P0: typed price survives
  assert.equal(first.items[0].kaina_source, 'manual');
  assert.equal(first.items[1].kaina, 6);

  const listV2 = [
    { aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 8 },
    { aprasymas: 'Lubų dažymas', vnt: 'm²', kaina: 6.5 },
  ];
  const second = applyPriceListToPositions(first.items, listV2);
  assert.equal(second.items[0].kaina, 40);         // manual still survives re-apply
  assert.equal(second.items[1].kaina, 6.5);        // kainynas price updates on re-apply
});

// ═══════════════════════════════════════════════════════════════════════════
// Task 5 (2026-09-02) — "tokia pati arba panaši" matching, table-driven.
// Every description below is invented; none of it comes from a client file.
// ═══════════════════════════════════════════════════════════════════════════

const M2 = 'm²';

// Each case: [name, pozicija aprašymas, price-list rows, expected kaina|null]
const MATCH_CASES = [
  [
    'diacritics: a kainynas typed without LT letters still prices the row',
    'Sienų glaistymas Q2', [{ aprasymas: 'Sienu glaistymas Q2', vnt: M2, kaina: 5.4 }], 5.4,
  ],
  [
    'diacritics: the reverse direction works too',
    'Sienu dazymas', [{ aprasymas: 'Sienų dažymas', vnt: M2, kaina: 7.1 }], 7.1,
  ],
  [
    'Q-levels stay distinct — Q4 must not be priced from the Q2 line',
    'Sienų glaistymas Q4',
    [
      { aprasymas: 'Sienų glaistymas Q2', vnt: M2, kaina: 5 },
      { aprasymas: 'Sienų glaistymas Q4', vnt: M2, kaina: 9 },
    ],
    9,
  ],
  [
    'coat count stays distinct — 2 sluoksniai gets the 2-sluoksniai price',
    'Sienų dažymas (2 sluoksniai)',
    [
      { aprasymas: 'Sienų dažymas (1 sluoksnis)', vnt: M2, kaina: 4 },
      { aprasymas: 'Sienų dažymas (2 sluoksniai)', vnt: M2, kaina: 6.5 },
    ],
    6.5,
  ],
  [
    'height tier suffix still matches the plain kainynas line',
    'Sienų dažymas (iki 3m aukščio)',
    [{ aprasymas: 'Sienų dažymas', vnt: M2, kaina: 7.5 }], 7.5,
  ],
  [
    'GKP naming variant: extra thickness spec does not block the match',
    'GKP pertvarų montavimas',
    [{ aprasymas: 'GKP pertvarų montavimas, 12,5 mm', vnt: M2, kaina: 18 }], 18,
  ],
  [
    'GKP naming variant: punctuation and dashes do not block the match',
    'GKP lubų montavimas — 9,5 mm',
    [{ aprasymas: 'GKP lubų montavimas, 9,5 mm', vnt: M2, kaina: 21 }], 21,
  ],
  [
    'unit mismatch never fills, however identical the text',
    'Grindjuosčių montavimas',
    [{ aprasymas: 'Grindjuosčių montavimas', vnt: M2, kaina: 4 }], null,
  ],
  [
    'm³ price never lands on an m² row',
    'Betonavimas',
    [{ aprasymas: 'Betonavimas', vnt: 'm³', kaina: 120 }], null,
  ],
  [
    'unrelated work stays empty',
    'Vėdinimo sistemos montavimas',
    [{ aprasymas: 'Sienų dažymas', vnt: M2, kaina: 7.5 }], null,
  ],
];

for (const [name, aprasymas, items, expected] of MATCH_CASES) {
  test(`match: ${name}`, () => {
    // The pozicija is quoted in m² / m throughout; the unit-mismatch rows below
    // deliberately keep m² so ONLY the unit differs.
    const vnt = aprasymas === 'Grindjuosčių montavimas' ? 'm' : M2;
    const out = applyPriceListToPositions(
      [{ aprasymas, vnt, kiekis: 10 }], items,
    );
    if (expected === null) {
      assert.equal(out.applied, 0, `expected no fill, got ${out.items[0].kaina}`);
      assert.equal(out.items[0].kaina, undefined);
    } else {
      assert.equal(out.applied, 1, 'expected a fill');
      assert.equal(out.items[0].kaina, expected);
      assert.equal(out.items[0].kaina_source, 'kainynas');
    }
  });
}

test('ambiguity: two equally-good candidates at different prices fill nothing', () => {
  const poz = [{ aprasymas: 'Sienų dažymas', vnt: M2, kiekis: 10 }];
  const list = [
    { aprasymas: 'Sienų dažymas (iki 3m aukščio)', vnt: M2, kaina: 7 },
    { aprasymas: 'Sienų dažymas (virš 3m aukščio)', vnt: M2, kaina: 11 },
  ];
  const out = applyPriceListToPositions(poz, list);
  assert.equal(out.applied, 0);
  assert.equal(out.items[0].kaina, undefined);
  assert.equal(out.ambiguous.length, 1);
  assert.equal(out.ambiguous[0].aprasymas, 'Sienų dažymas');
  assert.equal(out.ambiguous[0].candidates.length, 2);
});

test('ambiguity: a duplicated line at the SAME price is not ambiguous', () => {
  const poz = [{ aprasymas: 'Sienų dažymas', vnt: M2, kiekis: 10 }];
  const list = [
    { aprasymas: 'Sienų dažymas', vnt: M2, kaina: 7 },
    { aprasymas: 'Sienu dazymas', vnt: M2, kaina: 7 },
  ];
  const out = applyPriceListToPositions(poz, list);
  assert.equal(out.applied, 1);
  assert.equal(out.items[0].kaina, 7);
  assert.equal(out.ambiguous.length, 0);
});

test('bestMatchForPozicija reports the ambiguity instead of guessing', () => {
  const m = bestMatchForPozicija(
    { aprasymas: 'Sienų dažymas', vnt: M2 },
    [
      { aprasymas: 'Sienų dažymas, vidus', vnt: M2, kaina: 7 },
      { aprasymas: 'Sienų dažymas, išorė', vnt: M2, kaina: 12 },
    ],
  );
  assert.equal(m.ambiguous, true);
  assert.equal(m.item, undefined);
});

test('tiers: exact and similar are counted separately', () => {
  const poz = [
    { aprasymas: 'Sienų dažymas', vnt: M2, kiekis: 10 },
    { aprasymas: 'Lubų dažymas (iki 3m aukščio)', vnt: M2, kiekis: 10 },
    { aprasymas: 'Nieko panašaus nėra', vnt: M2, kiekis: 1 },
  ];
  const list = [
    { aprasymas: 'Sienų dažymas', vnt: M2, kaina: 7 },
    { aprasymas: 'Lubų dažymas', vnt: M2, kaina: 6 },
  ];
  const out = applyPriceListToPositions(poz, list);
  assert.equal(out.exact, 1);
  assert.equal(out.similar, 1);
  assert.equal(out.applied, 2);
  assert.equal(out.skipped, 1);
});

test('onlyEmpty: an existing kainynas price is left alone', () => {
  const poz = [{
    aprasymas: 'Sienų dažymas', vnt: M2, kiekis: 10,
    kaina: 7, kaina_source: 'kainynas',
  }];
  const out = applyPriceListToPositions(
    poz, [{ aprasymas: 'Sienų dažymas', vnt: M2, kaina: 9 }], { onlyEmpty: true },
  );
  assert.equal(out.applied, 0);
  assert.equal(out.items[0].kaina, 7);
  // …while the manual button (no onlyEmpty) still refreshes it.
  const refreshed = applyPriceListToPositions(
    poz, [{ aprasymas: 'Sienų dažymas', vnt: M2, kaina: 9 }],
  );
  assert.equal(refreshed.items[0].kaina, 9);
});

test('onlyEmpty never overwrites a hand-typed price either', () => {
  const poz = [{
    aprasymas: 'Sienų dažymas', vnt: M2, kiekis: 10,
    kaina: 40, kaina_source: 'manual',
  }];
  const out = applyPriceListToPositions(
    poz, [{ aprasymas: 'Sienų dažymas', vnt: M2, kaina: 9 }], { onlyEmpty: true },
  );
  assert.equal(out.items[0].kaina, 40);
  assert.equal(out.items[0].kaina_source, 'manual');
});

// ── automatic fill after an extraction ──────────────────────────────────────

const DEFAULT_LIST = {
  id: 'pl-1', name: 'Mano kainynas', is_default: true,
  items: [
    { aprasymas: 'Sienų dažymas', mato_vnt: M2, kaina: 7.5 },
    { aprasymas: 'Lubų dažymas', mato_vnt: M2, kaina: 6 },
  ],
};

test('findDefaultPriceList ignores a default with no rows', () => {
  assert.equal(findDefaultPriceList([{ id: 'x', is_default: true, items: [] }]), null);
  assert.equal(findDefaultPriceList([DEFAULT_LIST]).id, 'pl-1');
  assert.equal(findDefaultPriceList([]), null);
});

test('auto-fill prices the fresh list and stamps the marker', () => {
  const project = {
    darbu_sarasas: [
      { aprasymas: 'Sienų dažymas', vnt: M2, kiekis: 100 },
      { aprasymas: 'Lubų dažymas', vnt: M2, kiekis: 50 },
      { aprasymas: 'Egzotinis darbas', vnt: M2, kiekis: 1 },
    ],
  };
  const out = autoFillFromDefaultPriceList(project, [DEFAULT_LIST]);
  assert.ok(out);
  assert.equal(out.summary.applied, 2);
  assert.equal(out.summary.name, 'Mano kainynas');
  assert.equal(out.project.darbu_sarasas[0].kaina, 7.5);
  assert.equal(out.project.darbu_sarasas[0].suma, 750);
  assert.equal(out.project.darbu_sarasas[1].suma, 300);
  assert.equal(out.project.darbu_sarasas[2].kaina, undefined);
  assert.equal(out.project._kainynas_auto_applied.id, 'pl-1');
  // Input untouched.
  assert.equal(project.darbu_sarasas[0].kaina, undefined);
});

test('auto-fill fires exactly once — the marker survives a reload', () => {
  const project = {
    darbu_sarasas: [{ aprasymas: 'Sienų dažymas', vnt: M2, kiekis: 100 }],
  };
  const first = autoFillFromDefaultPriceList(project, [DEFAULT_LIST]);
  assert.ok(first);
  // Second pass over the SAVED project (marker included) does nothing, even
  // though the row list still has fillable rows.
  assert.equal(autoFillFromDefaultPriceList(first.project, [DEFAULT_LIST]), null);
});

test('auto-fill does nothing without a default kainynas', () => {
  const project = { darbu_sarasas: [{ aprasymas: 'Sienų dažymas', vnt: M2, kiekis: 1 }] };
  const notDefault = { ...DEFAULT_LIST, is_default: false };
  assert.equal(autoFillFromDefaultPriceList(project, [notDefault]), null);
  assert.equal(autoFillFromDefaultPriceList(project, []), null);
  assert.equal(autoFillFromDefaultPriceList(null, [DEFAULT_LIST]), null);
});

test('auto-fill never touches a price the user already entered', () => {
  const project = {
    darbu_sarasas: [
      { aprasymas: 'Sienų dažymas', vnt: M2, kiekis: 100, kaina: 40, kaina_source: 'manual' },
      { aprasymas: 'Lubų dažymas', vnt: M2, kiekis: 50 },
    ],
  };
  const out = autoFillFromDefaultPriceList(project, [DEFAULT_LIST]);
  assert.equal(out.project.darbu_sarasas[0].kaina, 40);
  assert.equal(out.project.darbu_sarasas[0].kaina_source, 'manual');
  assert.equal(out.project.darbu_sarasas[1].kaina, 6);
  assert.equal(out.summary.applied, 1);
});

test('auto-fill returns null when nothing matched (no marker, no toast)', () => {
  const project = { darbu_sarasas: [{ aprasymas: 'Visai kitas darbas', vnt: M2, kiekis: 1 }] };
  assert.equal(autoFillFromDefaultPriceList(project, [DEFAULT_LIST]), null);
});

test('auto-fill also prices a KŽ project (rows[])', () => {
  const kz = { rows: [{ aprasymas: 'Sienų dažymas', mato_vnt: M2, kiekis: 10 }] };
  const out = autoFillFromDefaultPriceList(kz, [DEFAULT_LIST]);
  assert.equal(out.project.rows[0].kaina, 7.5);
  assert.equal(out.project.rows[0].suma, 75);
});

// ── the ambiguous rows are NAMED, not just counted (2026-09-02) ──────────────
//
// `applyPriceListToPositions` has always returned {aprasymas, candidates} per
// row it refused to price, and all three call sites passed only the count on to
// the toast — so the user was told "3 rows need a price by hand" with no way to
// find WHICH three in an 80-row sąmata.

const tRows = (_key, vars) => vars.rows;

test('describeAmbiguous names the rows the matcher refused to price', () => {
  const list = [
    { aprasymas: 'Sienų glaistymas Q2', candidates: [] },
    { aprasymas: 'Sienų glaistymas Q4', candidates: [] },
  ];
  assert.equal(describeAmbiguous(list, tRows),
    'Sienų glaistymas Q2 · Sienų glaistymas Q4');
});

test('describeAmbiguous truncates a long list instead of flooding the toast', () => {
  const list = Array.from({ length: 9 }, (_, i) => ({ aprasymas: `Eilutė ${i + 1}` }));
  const out = describeAmbiguous(list, tRows);
  assert.ok(out.endsWith('…'), out);
  assert.equal(out.split(' · ').length, AMBIGUOUS_ROWS_SHOWN);
});

test('describeAmbiguous returns undefined when there is nothing to name', () => {
  assert.equal(describeAmbiguous([], tRows), undefined);
  assert.equal(describeAmbiguous(undefined, tRows), undefined);
  assert.equal(describeAmbiguous([{ candidates: [] }], tRows), undefined);
});

test('the ambiguity guard really does report the row it skipped', () => {
  // End-to-end: two price lines within the margin at DIFFERENT prices → the
  // row must come back named, not silently folded into "praleista".
  const out = applyPriceListToPositions(
    [{ aprasymas: 'Sienų glaistymas', vnt: 'm²', kiekis: 10 }],
    [{ aprasymas: 'Sienų glaistymas Q2', vnt: 'm²', kaina: 6 },
     { aprasymas: 'Sienų glaistymas Q4', vnt: 'm²', kaina: 11 }],
  );
  assert.equal(out.applied, 0);
  assert.deepEqual(out.ambiguous.map(a => a.aprasymas), ['Sienų glaistymas']);
  assert.equal(describeAmbiguous(out.ambiguous, tRows), 'Sienų glaistymas');
});

test('scorePair: a wordier sąmata line that covers every word of ours is similar (stemmed overlap)', () => {
  // the same work in the contractor's words — every one of OUR tokens is in his line
  assert.ok(scorePair('LED nišų glaistymas/dažymas', 'Nišų iš GKP paslėptam led apšvietimui glaistymas dažymas') >= 0.78);
  assert.ok(scorePair('Sienų glaistymas/dažymas', 'Sienų, lubų glaistymas/dažymas') >= 0.78, 'his one line prices our two');
  // inflection does not break the match
  assert.ok(scorePair('Grindų plytelių klijavimas', 'Grindų plytelės klijavimo darbai') >= 0.78);
  // the overlap never reaches the exact tier
  assert.ok(scorePair('Sienų glaistymas/dažymas', 'Sienų, lubų glaistymas/dažymas') < 0.92);
  // one word of four differs → not the same work (a floor-tile row must never take a wall-tile price)
  assert.ok(scorePair('Nuolydžio formavimas dušo zonoje', 'Nuolydžio formavimas dušo kabinoje') < 0.78);
  assert.ok(scorePair('Sienų lyginimas Knauf Rotband', 'Sienų lyginimas sausu gipsiniu tinku "Rotband"') < 0.78);
  // two-token labels are not overlapped at all
  assert.ok(scorePair('Durų montavimas', 'Durų dažymas') < 0.78);
  assert.ok(scorePair('Grindjuosčių sumontavimas', 'Grindjuosčių dažymas') < 0.78);
  assert.ok(scorePair('Vonios sienų plytelių fugavimas', 'Plytelių klijavimas ant sienų ir grindų') < 0.78, 'fugavimas is not klijavimas');
});
