import test from 'node:test';
import assert from 'node:assert/strict';
import {
  blankReasonOf, describeScale, provenanceExplanation, provenancePhrase, provenanceText, scaleProvenanceLine, scaleStateWord,
} from './scaleProvenance.js';
import { confirmedLaneScale, laneScalesOf, METERS_PER_POINT_AT_1_TO_1 } from './durableScale.js';
import { isBannedText } from './userText.js';
import { makeT } from './testT.js';

const t = makeT('lt');
const en = makeT('en');
const PT = METERS_PER_POINT_AT_1_TO_1;
const mpp = (n) => Math.round(n * PT * 1e6) / 1e6;

// The backend's record, exactly as backend/geometry/scale.py `lane_record` writes it into
// `_meta.geometrija.masteliai[page]` (fields: saltinis, patikimumas, tekstas, is_lapo, pastaba; texts are the
// ones scale.py builds and backend/tests/test_geometry_scale.py asserts).
const lane = (ratio, rec) => laneScalesOf({ _meta: { geometrija: { masteliai: { 1: { m_per_pt: mpp(ratio), mastelis: ratio, ...rec } } } } })[1];
const text = (s, opts) => provenanceText(describeScale(s, opts), t);

test('objektas_i sheet 4 (real stored record): measured from 139 strings — read, never „spėjamas"', () => {
  const s = lane(75, { saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '139 matmenų eilutės ant matmenų linijų' });
  const d = describeScale(s);
  assert.equal(d.state, 'nuskaitytas');
  assert.equal(d.line, 'solid');
  assert.equal(provenanceText(d, t), '1:75 — iš plano matmenų (139 skaičiai)');
  assert.equal(scaleProvenanceLine(s, t), 'Mastelis 1:75 — iš plano matmenų (139 skaičiai)');
  assert.doesNotMatch(provenanceExplanation(d, t), /spėj/i);
  // Lithuanian count agreement
  assert.equal(text(lane(75, { saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '14 matmenų eilutės ant matmenų linijų' })), '1:75 — iš plano matmenų (14 skaičių)');
  assert.equal(text(lane(75, { saltinis: 'dimension_lines', patikimumas: 'medium', tekstas: '21 matmenų eilutės ant matmenų linijų' })), '1:75 — iš plano matmenų (21 skaičius)');
});

test('written on the sheet and confirmed — by the dimensions, by another sheet, by strings in other units', () => {
  assert.equal(text(lane(75, { saltinis: 'stated', patikimumas: 'high', tekstas: 'M 1:75 (patvirtina 4 lapo matmenys)', is_lapo: 4 })),
    '1:75 — užrašytas brėžinyje, patvirtintas 4 lapo matmenimis');
  assert.equal(text(lane(100, { saltinis: 'stated', patikimumas: 'high', tekstas: 'M 1:100 (matmenys užrašyti kitais vienetais — patvirtina mastelį)' })),
    '1:100 — užrašytas brėžinyje, patvirtintas matmenimis');
  // strings matched to the walls that land on the written scale
  const walls = lane(50, { saltinis: 'dimension_walls', patikimumas: 'high', tekstas: '12 matmenų eilutės atitinka sienas (1200, 2400); sutampa su užrašytu M 1:50' });
  assert.equal(text(walls), '1:50 — užrašytas brėžinyje, patvirtintas matmenimis');
  assert.equal(describeScale(walls).state, 'nuskaitytas');
});

test('written but nothing confirms it (LOW): a proposal that asks to be checked', () => {
  const s = lane(50, { saltinis: 'stated', patikimumas: 'low', tekstas: 'M 1:50 (užrašytas, nepatikrintas)' });
  const d = describeScale(s);
  assert.equal(d.state, 'spejamas');
  assert.equal(d.line, 'dashed');
  assert.equal(provenanceText(d, t), '1:50 — užrašytas, nepatikrintas — patikrinkite');
});

test('measured, and the written scale disagrees — both named', () => {
  const pastaba = 'Lape užrašytas mastelis 1:50, bet matmenys atitinka 1:60 — lapas tikriausiai spausdintas kitu dydžiu.';
  const s = lane(60, { saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '40 matmenų eilutės ant matmenų linijų', pastaba });
  const d = describeScale(s);
  assert.equal(provenanceText(d, t), '1:60 — išmatuotas; užrašytas 1:50 neatitinka');
  assert.equal(d.state, 'nuskaitytas');
  assert.match(provenanceExplanation(d, t), /spausdintas kitu dydžiu/, 'the backend\'s own note is in the card');
  // objektas_j2: the walls measure 1:45, the sheet writes 1:40
  const j2 = lane(45, { saltinis: 'dimension_walls', patikimumas: 'medium', tekstas: '24 matmenų eilutės atitinka sienas (…)',
    pastaba: 'Lape užrašytas mastelis 1:40, bet matmenys atitinka 1:45 — lapas tikriausiai spausdintas kitu dydžiu.' });
  assert.equal(text(j2), '1:45 — išmatuotas; užrašytas 1:40 neatitinka');
});

test('borrowed from a sibling sheet — its number, and a written scale it contradicts', () => {
  assert.equal(text(lane(40, { saltinis: 'sibling', patikimumas: 'medium', tekstas: 'iš 1 lapo (sienos sutampa; 30 matmenų eilutės ant matmenų linijų)', is_lapo: 1 })),
    '1:40 — iš 1 lapo');
  assert.equal(text(lane(45, { saltinis: 'sibling', patikimumas: 'medium', tekstas: 'iš 1 lapo (sienos sutampa; dimension_walls)', is_lapo: 1,
    pastaba: 'Lape užrašytas M 1:40, bet to paties plano 1 lapo matmenys atitinka 1:45 — rinkinys tikriausiai spausdintas kitu dydžiu.' })),
  '1:45 — iš 1 lapo; užrašytas 1:40 neatitinka');
  assert.equal(text(lane(75, { saltinis: 'sibling', patikimumas: 'medium', tekstas: 'iš to paties plano lapo' })), '1:75 — iš kito to paties plano lapo');
});

test('his own line over a dimension string', () => {
  const s = lane(50, { saltinis: 'user_line', patikimumas: 'high', tekstas: '4280' });
  assert.equal(text(s), '1:50 — jūsų nubrėžta linija ant „4280“');
  assert.equal(text(lane(50, { saltinis: 'user_line', patikimumas: 'high' })), '1:50 — jūsų nubrėžta linija');
});

test('no scale: the reason from masteliai_tusti', () => {
  const reason = 'Šiame lape nėra nei užrašyto mastelio, nei matmenų teksto. Nubrėžkite liniją ant žinomo matmens, kad nustatytumėte mastelį.';
  const project = { _meta: { geometrija: { masteliai: {}, masteliai_tusti: { 6: reason } } } };
  assert.equal(blankReasonOf(project, 6), reason);
  assert.equal(blankReasonOf(project, '6'), reason);
  assert.equal(blankReasonOf(project, 7), '');
  const d = describeScale(null, { blankReason: blankReasonOf(project, 6) });
  assert.equal(d.state, 'nenustatytas');
  assert.equal(provenanceText(d, t), `mastelio nėra — ${reason}`);
  assert.equal(scaleProvenanceLine(null, t, { blankReason: reason }), `Mastelio nėra — ${reason}`);
  assert.equal(provenanceText(describeScale(undefined), t), 'mastelio nėra');
});

test('„spėjamas" only for low confidence or no backend source', () => {
  // an older blob: no saltinis — the lane scale is a guess, and no longer claims „užrašytas brėžinyje"
  const old = lane(75, {});
  assert.equal(describeScale(old).state, 'spejamas');
  assert.equal(text(old), '1:75 — spėjamas pagal plano matmenis');
  // the OCR lane's weak agreement
  const weak = lane(100, { saltinis: 'dimension_lines', patikimumas: 'low', tekstas: '6 matmenų eilutės ant matmenų linijų (…); skaičiai perskaityti iš lapo vaizdo',
    pastaba: 'Matmenys tarpusavyje sutampa tik apytiksliai — patikrinkite mastelį, nubrėžę liniją ant žinomo matmens.' });
  const dw = describeScale(weak);
  assert.equal(dw.state, 'spejamas');
  assert.equal(provenanceText(dw, t), '1:100 — spėjamas iš plano matmenų — patikrinkite');
  assert.match(provenanceExplanation(dw, t), /iš lapo vaizdo/);
  // the rooms' areas
  const auto = { metersPerPointX: 105 * PT, metersPerPointY: 105 * PT, calibrated: true, source: 'auto' };
  assert.equal(describeScale(auto).state, 'spejamas');
  assert.equal(text(auto), '~1:105 — spėjamas pagal patalpų plotus');
  // every source with high / medium is read
  for (const saltinis of ['dimension_lines', 'dimension_walls', 'stated', 'sibling', 'user_line']) {
    for (const patikimumas of ['high', 'medium']) {
      const d = describeScale(lane(50, { saltinis, patikimumas, tekstas: '12 matmenų eilutės ant matmenų linijų', is_lapo: 2 }));
      assert.equal(d.state, 'nuskaitytas', `${saltinis}/${patikimumas}`);
      assert.doesNotMatch(provenanceText(d, t), /spėj/i, `${saltinis}/${patikimumas}`);
    }
  }
});

test('confirming keeps where it came from; his own clicks say so', () => {
  const read = lane(75, { saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '139 matmenų eilutės ant matmenų linijų' });
  const mine = confirmedLaneScale(read, 0);
  assert.deepEqual(mine.provenance, read.provenance);
  const d = describeScale(mine);
  assert.equal(d.state, 'patvirtintas');
  assert.equal(provenanceText(d, t), '1:75 — iš plano matmenų (139 skaičiai); patvirtinote jūs');
  assert.equal(text(confirmedLaneScale(lane(75, {}), 0)), '1:75 — patvirtinote jūs');
  const user = { metersPerPointX: 50 * PT, metersPerPointY: 50 * PT, calibrated: true, source: 'user', label: '1:50' };
  assert.equal(text(user), '1:50 — jūsų nustatytas pagal žinomą ilgį');
  assert.equal(describeScale(user).state, 'patvirtintas');
});

test('a record of another ratio than the page shows carries no provenance', () => {
  // the pair lane read 1:50 on the sheet, the geometry lane 1:82 — the record says nothing about 1:50
  const project = { _meta: {
    plan_dimension_lane: { mastelis: { 1: 50 } },
    geometrija: { masteliai: { 1: { m_per_pt: mpp(82), mastelis: 82, saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '20 matmenų eilutės ant matmenų linijų' } } },
  } };
  const s = laneScalesOf(project)[1];
  assert.equal(s.label, '1:50');
  assert.equal(s.provenance, undefined);
  assert.equal(describeScale(s).state, 'spejamas');
});

test('an odd ratio is explained, not hidden', () => {
  const d = describeScale(lane(115, { saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '60 matmenų eilutės ant matmenų linijų' }));
  assert.match(provenanceExplanation(d, t), /1:115 nėra įprastas braižymo mastelis/);
});

test('words: none banned, none a raw key, the English catalogue mirrors every one', () => {
  const recs = [
    {}, { saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '139 matmenų eilutės ant matmenų linijų' },
    { saltinis: 'dimension_walls', patikimumas: 'medium', tekstas: '9 matmenų eilutės atitinka sienas', pastaba: 'Lape užrašytas mastelis 1:40, bet matmenys atitinka 1:45 — x.' },
    { saltinis: 'stated', patikimumas: 'low', tekstas: 'M 1:50 (užrašytas, nepatikrintas)' },
    { saltinis: 'stated', patikimumas: 'high', is_lapo: 3 }, { saltinis: 'sibling', patikimumas: 'medium', is_lapo: 1 },
    { saltinis: 'sibling', patikimumas: 'medium' }, { saltinis: 'user_line', patikimumas: 'high', tekstas: '4280' },
    { saltinis: 'dimension_lines', patikimumas: 'low', tekstas: 'skaičiai perskaityti iš lapo vaizdo' },
  ];
  const scales = [
    ...recs.map((r) => lane(50, r)), ...recs.map((r) => confirmedLaneScale(lane(50, r), 0)), null,
    { metersPerPointX: 0.03, calibrated: true, source: 'auto' }, { metersPerPointX: 0.03, calibrated: true, source: 'user' },
    { metersPerPointX: 0.03, calibrated: true, source: 'standard', label: '1:85' },
  ];
  for (const s of scales) {
    for (const tr of [t, en]) {
      const d = describeScale(s, { blankReason: 'Priežastis.' });
      for (const str of [provenanceText(d, tr), provenancePhrase(d, tr), provenanceExplanation(d, tr), scaleProvenanceLine(s, tr), scaleStateWord(d.state, tr)]) {
        assert.ok(str && !/project\.scaleProvenance/.test(str), `raw key or empty: „${str}"`);
        if (tr === t) assert.equal(isBannedText(str), false, str);
      }
    }
  }
});
