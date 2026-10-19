import test from 'node:test';
import assert from 'node:assert/strict';
import { toJSON, fromJSON, toMeasurementsCSV } from './measureExport.js';

const scale = { metersPerPointX: 0.05, metersPerPointY: 0.05, calibrated: true };
const doc = {
  measurements: [
    { id: 'a', kind: 'distance', page: 1, points: [{x:0,y:0},{x:200,y:0}], confidence:'green', source:'user' },
    { id: 'b', kind: 'area', page: 1, points: [{x:0,y:0},{x:200,y:0},{x:200,y:100},{x:0,y:100}], confidence:'amber', source:'user' },
    { id: 'c', kind: 'count', page: 1, points: [{x:5,y:5}], typeId: 'rozetes' },
    { id: 'd', kind: 'count', page: 1, points: [{x:9,y:9}], typeId: 'rozetes' },
  ],
  measureScales: { 1: scale },
  countTypes: [{ id: 'rozetes', label: 'Rozetės' }],
  display: { decimals: 2 },
};

test('CSV: header + 2 measurement rows + 1 count-tally row', () => {
  const csv = toMeasurementsCSV(doc);
  const lines = csv.split('\r\n');
  assert.equal(lines.length, 4);                 // header + distance + area + count tally
  assert.ok(lines[0].startsWith('Lapas;Tipas'));
  assert.ok(/Atstumas;.*;10,00;m/.test(lines[1]));   // 200pt @ 0.05 = 10 m
  assert.ok(/Plotas;.*;50,00;m²;30,00;m/.test(lines[2])); // area 50 m², perim 30 m
  assert.ok(/Skaičius;Rozetės;2;vnt\./.test(lines[3]));   // 2 count markers
});
test('JSON round-trips', () => {
  const back = fromJSON(toJSON(doc));
  assert.equal(back.measurements.length, 4);
});
test('fromJSON rejects garbage', () => {
  assert.throws(() => fromJSON('{"nope":1}'));
});
test('CSV: a „Pastaba" pin is its own row with its text — never a length (W5-C C11)', () => {
  const csv = toMeasurementsCSV({ ...doc, measurements: [{ id: 'n', kind: 'note', page: 2, points: [{ x: 1, y: 1 }], text: 'Patikrinti aukštį', source: 'user' }] });
  const lines = csv.split('\r\n');
  assert.equal(lines.length, 2);
  assert.ok(lines[1].startsWith('2;Pastaba;Patikrinti aukštį;'));
  assert.ok(!/Atstumas/.test(csv));
});
