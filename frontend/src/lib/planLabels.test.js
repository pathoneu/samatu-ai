import test from 'node:test';
import assert from 'node:assert/strict';
import { nextRoomNr, roomFromPlanLabel, unclaimedPlanLabels } from './planLabels.js';

const project = {
  id: 'p',
  patalpos: [
    { nr: '01', plotas_m2: 37.86, _plotas_uzrasas: { page: 4, value_m2: 37.86 } },
    { nr: '09', plotas_m2: 6.78, _plotas_uzrasas: { page: 4, value_m2: 6.78 } },
  ],
  _meta: { plan_area_lane: { unclaimed: [
    { page: 4, value_m2: 6.9, bbox: [300, 850, 340, 860], page_width: 1000, page_height: 1000 },
    { page: 4, value_m2: 3.6, bbox: [150, 820, 190, 830], page_width: 1000, page_height: 1000 },
    { page: 4, value_m2: 6.78, bbox: [1, 1, 2, 2], page_width: 1000, page_height: 1000 },
  ] } },
};

test('unclaimedPlanLabels hides a label a room already carries', () => {
  assert.deepEqual(unclaimedPlanLabels(project).map((u) => u.value_m2), [6.9, 3.6]);
  assert.deepEqual(unclaimedPlanLabels({}), []);
});

test('nextRoomNr follows the project numbering style', () => {
  assert.equal(nextRoomNr(project.patalpos), '10');
  assert.equal(nextRoomNr([{ nr: '101' }, { nr: '102' }]), '103');
  assert.equal(nextRoomNr([]), '01');
});

test('roomFromPlanLabel carries the label as the area and sits where it stands', () => {
  const room = roomFromPlanLabel(project, unclaimedPlanLabels(project)[0]);
  assert.equal(room.nr, '10');
  assert.equal(room.plotas_m2, 6.9);
  assert.equal(room.plotas_saltinis, 'plano_uzrasas');
  assert.equal(room.puslapio_nr, 4);
  assert.equal(room._prideta_is_plano, true);
  assert.ok(room.bbox_pct.x0 < 0.32 && room.bbox_pct.x1 > 0.32 && room.bbox_pct.y0 < 0.855 && room.bbox_pct.y1 > 0.855);
  assert.equal(room.paskirtis, null, 'the purpose is his to set, not a guess');
});
