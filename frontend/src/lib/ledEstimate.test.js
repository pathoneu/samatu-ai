import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { estimatedLedRooms, ledEstimateBilled, ledEstimateText } from './ledEstimate.js';

const HERE = dirname(fileURLToPath(import.meta.url));

const niche = (ilgis_m, source) => ({ tipas: 'nisa_LED', kiekis: 1, ilgis_m, _source: source });

const ROOMS = [
  { nr: '102', pavadinimas: 'Svetainė', elementai: [niche(8, 'niche_locator')] },
  { nr: '103', pavadinimas: 'Koridorius', elementai: [niche(7.7, 'statistical_inference')] },
  { nr: '106', pavadinimas: 'Skalbykla', elementai: [niche(6.3, 'statistical_inference')] },
  { nr: '107', pavadinimas: 'Vonia', elementai: [{ tipas: 'duris', kiekis: 1 }] },
];

test('the rooms with an estimate, in room order — a read niche is not one', () => {
  assert.deepEqual(estimatedLedRooms(ROOMS), [
    { label: '103', metres: 7.7 }, { label: '106', metres: 6.3 },
  ]);
  assert.deepEqual(ledEstimateText(estimatedLedRooms(ROOMS)), {
    rooms: '103 (7,70 m), 106 (6,30 m)', total: '14,00',
  });
});

test('a room his scope took out is not named (as on the blank row)', () => {
  const rooms = [
    { ...ROOMS[1], _neskaiciuoti: true },
    { ...ROOMS[2], _neskaiciuoti_sritys: ['apdaila'] },
  ];
  assert.deepEqual(estimatedLedRooms(rooms), []);
  assert.deepEqual(estimatedLedRooms([{ ...ROOMS[2], _neskaiciuoti_sritys: ['grindys'] }]),
    [{ label: '106', metres: 6.3 }]);
});

test('nothing estimated, or nothing at all — no choice to offer', () => {
  assert.deepEqual(estimatedLedRooms([ROOMS[0], ROOMS[3]]), []);
  assert.deepEqual(estimatedLedRooms(undefined), []);
  assert.deepEqual(ledEstimateText([]), { rooms: '', total: '0,00' });
});

test('the choice shows what the niche rows do right now', () => {
  // his answer, when he gave one
  assert.equal(ledEstimateBilled(ROOMS, true), true);
  assert.equal(ledEstimateBilled(ROOMS, false), false);
  // computed since 2026-10-06: the estimate waits (the backend marks the room)
  const waiting = ROOMS.map((r) => (r.nr === '103' || r.nr === '106' ? { ...r, _nisu_ivertinta_m: 7.7 } : r));
  assert.equal(ledEstimateBilled(waiting, undefined), false);
  // a project computed before that still bills it until its next recompute
  assert.equal(ledEstimateBilled(ROOMS, undefined), true);
  // nothing estimated: nothing billed
  assert.equal(ledEstimateBilled([ROOMS[0]], undefined), false);
});

test('the Nustatymai choice is worded for him, in both languages', () => {
  const lt = JSON.parse(readFileSync(join(HERE, '../i18n/lt.json'), 'utf8')).project.assumptions;
  const en = JSON.parse(readFileSync(join(HERE, '../i18n/en.json'), 'utf8')).project.assumptions;
  for (const a of [lt, en]) {
    for (const key of ['ledEstimate', 'ledEstimateNote', 'ledEstimateLeave', 'ledEstimateAccept']) {
      assert.equal(typeof a[key], 'string', key);
    }
    assert.match(a.ledEstimateNote, /\{\{rooms\}\}/);
    assert.match(a.ledEstimateNote, /\{\{total\}\}/);
    assert.equal(typeof a.ledEstimateTitles.true, 'string');
    assert.equal(typeof a.ledEstimateTitles.false, 'string');
  }
  // the words the backend's blank row sends him to
  assert.equal(lt.ledEstimate, 'LED nišos be perskaityto ilgio');
  assert.equal(lt.ledEstimateAccept, 'Priimti įvertinimą');
  assert.equal(lt.ledEstimateLeave, 'Palikti tuščią');
});
