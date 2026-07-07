import test from 'node:test';
import assert from 'node:assert/strict';
import { draftReducer } from './measureOverlayReducer.js';

test('area close on click-first within tolerance', () => {
  const d = { points: [{x:0,y:0},{x:10,y:0},{x:10,y:10}] };
  const r = draftReducer(d, { type: 'click', tool: 'area', point: { x: 0.5, y: 0.5 }, closeTolerance: 2 });
  assert.equal(r.committed, true);
  assert.equal(r.points.length, 3);            // does NOT append the closing click
});
test('distance appends vertices', () => {
  const r = draftReducer({ points: [{x:0,y:0}] }, { type: 'click', tool: 'distance', point: { x: 5, y: 0 } });
  assert.equal(r.points.length, 2);
  assert.equal(r.committed, false);
});
test('finish requires min vertices (area>=3, line>=2)', () => {
  assert.equal(draftReducer({points:[{x:0,y:0},{x:1,y:0}]}, {type:'finish', tool:'area'}).committed, false);
  assert.equal(draftReducer({points:[{x:0,y:0},{x:1,y:0}]}, {type:'finish', tool:'distance'}).committed, true);
});
test('undo drops last; reset clears', () => {
  assert.equal(draftReducer({points:[{x:0,y:0},{x:1,y:0}]}, {type:'undo'}).points.length, 1);
  assert.equal(draftReducer({points:[{x:0,y:0}]}, {type:'reset'}).points.length, 0);
});
