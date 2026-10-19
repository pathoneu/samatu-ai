import test from 'node:test';
import assert from 'node:assert/strict';
import {
  roomForToolClick, pickCandidates, retryNrFor, noWallSentence, proposalLines, rasterProposalLines, holesKept, commitBody, insideProposal, readOutlineProposal,
} from './roomTool.js';
import { noRoomZoneAt, NO_ROOM_ZONES } from './sheetZonesApi.js';

const square = (x0, y0, x1, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
// Sheet 1 and sheet 3 are one plan; sheet 3 is shifted by 0,04 to the right (objektas_h's sheet 3 is).
const SUT = {
  1: { base: 1, kx: 1, ky: 1, dx_pct: 0, dy_pct: 0 },
  3: { base: 1, kx: 1, ky: 1, dx_pct: 0.04, dy_pct: 0 },
  5: { base: 5, kx: 1, ky: 1, dx_pct: 0, dy_pct: 0 },
};
const ROOMS = [
  { nr: '04', pavadinimas: 'Virtuvė', plotas_m2: 26.31, puslapio_nr: 1, polygon_source: 'vektoriniai_konturai',
    polygon_pct: square(0.1, 0.1, 0.4, 0.4), _konturas: { page: 1 }, _vieta: { page: 1, cx: 0.25, cy: 0.25, saltinis: 'zenkliukas' } },
  { nr: '05', pavadinimas: 'Svetainė', plotas_m2: 35.5, puslapio_nr: 1,
    _vieta: { page: 1, cx: 0.6, cy: 0.25, saltinis: 'zenkliukas' } },
  { nr: '06', pavadinimas: 'Vaiko', puslapio_nr: 1, _vieta: { page: 1, cx: 0.6, cy: 0.7, saltinis: 'bbox' } },
  { nr: '09', puslapio_nr: 1, _sujungta_i: '04', _vieta: { page: 1, cx: 0.3, cy: 0.3, saltinis: 'zenkliukas' } },
];

test('the outline under the click names the room — on its own sheet and on another sheet of the same plan', () => {
  assert.deepEqual(roomForToolClick(ROOMS, { page: 1, x_pct: 0.2, y_pct: 0.2 }, { sutapdinimas: SUT }), { nr: '04', how: 'outline' });
  // on sheet 3 the same room sits 0,04 further left (base = sheet + d → sheet 3 point = base − 0,04)
  assert.deepEqual(roomForToolClick(ROOMS, { page: 3, x_pct: 0.08, y_pct: 0.2 }, { sutapdinimas: SUT }), { nr: '04', how: 'outline' });
  assert.notDeepEqual(roomForToolClick(ROOMS, { page: 3, x_pct: 0.38, y_pct: 0.2 }, { sutapdinimas: SUT }), { nr: '04', how: 'outline' });
});

test('with no outline under the click, the nearest printed number of this plan names it; a weak seat never does', () => {
  assert.deepEqual(roomForToolClick(ROOMS, { page: 1, x_pct: 0.55, y_pct: 0.3 }, { sutapdinimas: SUT }), { nr: '05', how: 'number' });
  // 06's seat is a guessed box: the click near it still goes to the nearest STRONG number (05)
  assert.deepEqual(roomForToolClick(ROOMS, { page: 1, x_pct: 0.6, y_pct: 0.7 }, { sutapdinimas: SUT }), { nr: '05', how: 'number' });
  // a merged room is never the answer, even with its number closest
  assert.notEqual(roomForToolClick(ROOMS, { page: 1, x_pct: 0.42, y_pct: 0.3 }, { sutapdinimas: SUT })?.nr, '09');
  // another plan (base 5): nothing of plan 1 lies there
  assert.equal(roomForToolClick(ROOMS, { page: 5, x_pct: 0.2, y_pct: 0.2 }, { sutapdinimas: SUT }), null);
  assert.equal(roomForToolClick([], { page: 1, x_pct: 0.2, y_pct: 0.2 }), null);
  assert.equal(roomForToolClick(ROOMS, { page: 1, x_pct: null, y_pct: 0.2 }), null);
});

test('„Kuri tai patalpa?" offers rooms without an outline first', () => {
  assert.deepEqual(pickCandidates(ROOMS).map((c) => c.nr), ['05', '06', '04']);
});

test('the server naming another room gives ONE retry with that room', () => {
  assert.equal(retryNrFor({ status: 'taken', nr: '05' }, '04'), '05');
  assert.equal(retryNrFor({ status: 'open', su: ['05'], plotas_m2: 40 }, '04'), '05');
  assert.equal(retryNrFor({ status: 'open', su: ['05', '06'] }, '04'), null);
  assert.equal(retryNrFor({ status: 'taken', nr: '04' }, '04'), null);
  assert.equal(retryNrFor({ status: 'outside' }, '04'), null);
  assert.equal(retryNrFor({ status: 'ok' }, '04'), null);
});

test('a click inside a room the walls do not separate from its neighbour says so, and where the fix is', () => {
  assert.equal(noWallSentence('04', { status: 'taken', nr: '03' }),
    'Patalpos 04 nuo patalpos 03 sienos neatskiria — kontūro pagal sienas čia nėra. '
    + 'Taisykite kontūrą viršūnėmis („Taisyti kontūrą") arba padalinkite erdvę patalpos lape.');
  assert.equal(noWallSentence('04', { status: 'taken', nr: '04' }), null);
  assert.equal(noWallSentence('04', { status: 'ok' }), null);
});

test('the consequence line: the outline against the table, and where the walls come from', () => {
  const answer = { status: 'ok', room: { _konturas: { plotas_m2: 26.3 }, perimetras_m: 21.4, perimetras_saltinis: 'matmenu_eilutes' } };
  assert.deepEqual(proposalLines(ROOMS[0], answer), {
    title: '04 Virtuvė · kontūras 26,30 m²',
    sub: 'lentelėje 26,31 m² · sienos 21,40 m pagal brėžinio matmenis',
  });
  assert.deepEqual(proposalLines({ nr: '07' }, { room: { _konturas: {} } }), { title: '07 · kontūras —', sub: null });
  assert.equal(rasterProposalLines(ROOMS[0], square(0, 0, 1, 1)).sub, 'Šiame lape sienų programa neperskaitė — kontūras apytikslis');
});

test('the commit keeps the holes that still fit inside the new outline, with his answers', () => {
  const room = {
    polygon_holes_pct: [square(0.15, 0.15, 0.17, 0.17), square(0.5, 0.5, 0.52, 0.52)],
    _konturas: { skyles: [{ sienos: false }, { sienos: true }] },
  };
  const ring = square(0.1, 0.1, 0.4, 0.4);
  assert.deepEqual(holesKept(room, ring), [{ ring: square(0.15, 0.15, 0.17, 0.17), sienos: false }]);
  assert.deepEqual(commitBody({ page: 1, ring }, room), {
    page: 1, polygon_pct: ring, holes: [square(0.15, 0.15, 0.17, 0.17)], holes_walls: [false], kaip: 'parodyta',
  });
  assert.deepEqual(commitBody({ page: 2, ring }, {}), { page: 2, polygon_pct: ring, kaip: 'parodyta' });
});

test('a click inside the pending proposal is a click on it', () => {
  const p = { page: 1, ring: square(0.1, 0.1, 0.4, 0.4) };
  assert.equal(insideProposal(p, { page: 1, x_pct: 0.2, y_pct: 0.2 }), true);
  assert.equal(insideProposal(p, { page: 1, x_pct: 0.5, y_pct: 0.2 }), false);
  assert.equal(insideProposal(p, { page: 2, x_pct: 0.2, y_pct: 0.2 }), false);
  assert.equal(insideProposal(null, { page: 1, x_pct: 0.2, y_pct: 0.2 }), false);
});

test('a click in the title block, a legend or a table is never a room (sheet zones, W1-E)', () => {
  const zones = { status: 'ok', zones: [
    { kind: 'planas', bbox_pct: [0.05, 0.05, 0.7, 0.9] },
    { kind: 'antspaudas', bbox_pct: [0.72, 0.7, 1, 1] },
    { kind: 'legenda', bbox_pct: [0.72, 0.1, 0.95, 0.4] },
    { kind: 'lentele', bbox_pct: [0.4, 0.6, 0.6, 0.8] },
    { kind: 'pastabos', bbox_pct: [0.72, 0.45, 0.95, 0.6] },
  ] };
  assert.deepEqual(noRoomZoneAt(zones, 0.8, 0.8), { kind: 'antspaudas', sentence: NO_ROOM_ZONES.antspaudas });
  assert.equal(noRoomZoneAt(zones, 0.8, 0.2).kind, 'legenda');
  // a table drawn inside the plan viewport is still a table
  assert.equal(noRoomZoneAt(zones, 0.5, 0.7).kind, 'lentele');
  // the plan is not refused; notes are refused outside every plan (W5-B B2), never inside one
  assert.equal(noRoomZoneAt(zones, 0.2, 0.2), null);
  assert.equal(noRoomZoneAt(zones, 0.8, 0.5).kind, 'pastabos');
  const notesInPlan = { status: 'ok', zones: [...zones.zones, { kind: 'pastabos', bbox_pct: [0.1, 0.62, 0.3, 0.66] }] };
  assert.equal(noRoomZoneAt(notesInPlan, 0.2, 0.64), null);
  // no zones known = nothing refused
  assert.equal(noRoomZoneAt({ status: 'no_text', zones: [] }, 0.8, 0.8), null);
  assert.equal(noRoomZoneAt(null, 0.8, 0.8), null);
});

// ── readOutlineProposal: what one click proposes (useRoomTool's reading, proposal first) ─────────────────
const WHERE = { page: 1, x_pct: 0.6, y_pct: 0.7 };
const byNr = (nr) => ROOMS.find((r) => String(r.nr) === String(nr)) || null;
const RING = square(0.5, 0.6, 0.7, 0.8);

test('readOutlineProposal: vector walls → a vector proposal with the consequence lines, the raster never asked', async () => {
  const asked = [];
  const out = await readOutlineProposal({
    nr: '06', where: WHERE, onPreview: async (nr) => { asked.push(nr); return { status: 'ok', room: { polygon_pct: RING, _konturas: { plotas_m2: 15.2 } } }; },
    onRasterPreview: async () => { throw new Error('raster must not be asked'); }, roomByNr: byNr,
  });
  assert.deepEqual(asked, ['06']);
  assert.equal(out.proposal.kind, 'vector');
  assert.equal(out.proposal.nr, '06');
  assert.deepEqual(out.proposal.ring, RING);
  assert.match(out.proposal.lines.title, /^06 Vaiko · kontūras 15,2/);
});

test('readOutlineProposal: no vector walls → the raster fill is PROPOSED (not saved), its lines say it is an estimate', async () => {
  const raster = [];
  const out = await readOutlineProposal({
    nr: '06', where: WHERE, onPreview: async () => ({ status: 'no_walls' }),
    onRasterPreview: async (nr, where) => { raster.push([nr, where]); return { ring: RING, data: { polygon_pdf: [[1, 2]] } }; },
    roomByNr: byNr,
  });
  assert.deepEqual(raster, [['06', WHERE]]);
  assert.equal(out.proposal.kind, 'raster');
  assert.deepEqual(out.proposal.ring, RING);
  assert.deepEqual(out.proposal.data, { polygon_pdf: [[1, 2]] });   // what the commit later saves
  assert.equal(out.proposal.page, 1);
  assert.equal(out.proposal.lines.title, '06 Vaiko · kontūras pagal brėžinio vaizdą');
  assert.match(out.proposal.lines.sub, /apytikslis/);
});

test('readOutlineProposal: the raster fallback finds nothing or fails → the no_walls answer is the failure to word', async () => {
  for (const onRasterPreview of [async () => null, async () => { throw new Error('click-to-fill 500'); }, async () => ({ ring: null })]) {
    const out = await readOutlineProposal({ nr: '06', where: WHERE, onPreview: async () => ({ status: 'no_walls' }), onRasterPreview, roomByNr: byNr });
    assert.deepEqual(out, { failure: { status: 'no_walls' } });
  }
  // no raster fallback wired at all → the same failure
  const none = await readOutlineProposal({ nr: '06', where: WHERE, onPreview: async () => ({ status: 'no_walls' }), roomByNr: byNr });
  assert.deepEqual(none, { failure: { status: 'no_walls' } });
});

test('readOutlineProposal: a guessed room the walls give to a neighbour is asked once more for that one; the raster follows the retried room', async () => {
  const asked = [];
  const out = await readOutlineProposal({
    nr: '05', where: WHERE, how: 'number',
    onPreview: async (nr) => { asked.push(nr); return nr === '05' ? { status: 'open', su: ['06'] } : { status: 'no_walls' }; },
    onRasterPreview: async (nr) => (nr === '06' ? { ring: RING, data: {} } : null), roomByNr: byNr,
  });
  assert.deepEqual(asked, ['05', '06']);
  assert.equal(out.proposal.kind, 'raster');
  assert.equal(out.proposal.nr, '06');
});

test('readOutlineProposal: no wall between the clicked outline and a neighbour → one sentence, nothing proposed', async () => {
  const out = await readOutlineProposal({ nr: '04', where: WHERE, how: 'outline', onPreview: async () => ({ status: 'taken', nr: '05' }), roomByNr: byNr });
  assert.match(out.error, /^Patalpos 04 nuo patalpos 05 sienos neatskiria/);
});

test('readOutlineProposal: he left the tool while it read (stale) → null after the outline answer and after the raster answer', async () => {
  let left = false;
  const afterOutline = await readOutlineProposal({
    nr: '06', where: WHERE, onPreview: async () => { left = true; return { status: 'ok', room: { polygon_pct: RING } }; }, roomByNr: byNr, stale: () => left,
  });
  assert.equal(afterOutline, null);
  left = false;
  const afterRaster = await readOutlineProposal({
    nr: '06', where: WHERE, onPreview: async () => ({ status: 'no_walls' }),
    onRasterPreview: async () => { left = true; return { ring: RING, data: {} }; }, roomByNr: byNr, stale: () => left,
  });
  assert.equal(afterRaster, null);
});
