import test from 'node:test';
import assert from 'node:assert/strict';
import { selfIntersects } from './polygonGeometry.js';

test('selfIntersects: simple square is not self-intersecting', () => {
  const square = [
    { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 },
  ];
  assert.equal(selfIntersects(square), false);
});

test('selfIntersects: bowtie is self-intersecting', () => {
  // Classic bowtie — edges (p0→p1) and (p2→p3) cross
  const bowtie = [
    { x: 0, y: 0 }, { x: 10, y: 10 }, { x: 10, y: 0 }, { x: 0, y: 10 },
  ];
  assert.equal(selfIntersects(bowtie), true);
});

test('selfIntersects: triangle is not self-intersecting', () => {
  const tri = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 5, y: 10 }];
  assert.equal(selfIntersects(tri), false);
});

test('selfIntersects: shared vertex between adjacent edges is allowed', () => {
  // Adjacent edges share a vertex — that's NOT self-intersection
  const square = [
    { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 },
  ];
  assert.equal(selfIntersects(square), false);
});
