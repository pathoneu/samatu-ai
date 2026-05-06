import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getConfirmableSymbolCounts,
  getSymbolPoints,
  getSymbolVisibleCount,
  removeSymbolPoint,
} from './symbolOverlay.js';

test('getSymbolPoints: keeps high and medium AI detections as reviewable draft points', () => {
  const result = {
    symbol_type: 'sviestuvai',
    symbols: [
      { x_pct: 0.25, y_pct: 0.35, confidence: 'high' },
      { x_pct: 0.45, y_pct: 0.55, confidence: 'medium' },
      { x_pct: 1.2, y_pct: 0.2, confidence: 'high' },
      { x_pct: 0.2, y_pct: Number.NaN, confidence: 'high' },
    ],
  };

  assert.deepEqual(getSymbolPoints(result), [
    { x_pct: 0.25, y_pct: 0.35, confidence: 'high', type: 'sviestuvai' },
    { x_pct: 0.45, y_pct: 0.55, confidence: 'medium', type: 'sviestuvai' },
  ]);
  assert.equal(getSymbolVisibleCount(result), 2);
});

test('getSymbolPoints: keeps medium template matches because the user picked the visual example', () => {
  const result = {
    symbol_type: 'template_symbol',
    matches: [
      { x_pct: 0.1, y_pct: 0.2, confidence: 'medium' },
      { x_pct: 0.9, y_pct: 0.8, confidence: 'low' },
    ],
  };

  assert.deepEqual(getSymbolPoints(result), [
    { x_pct: 0.1, y_pct: 0.2, confidence: 'medium', type: 'template_symbol' },
  ]);
});

test('getConfirmableSymbolCounts: counts only filtered points per type for bundled page scans', () => {
  const result = {
    symbol_type: 'page_scan',
    by_type: {
      sviestuvai: {
        symbols: [
          { x_pct: 0.2, y_pct: 0.3, confidence: 'high' },
          { x_pct: 0.21, y_pct: 0.31, confidence: 'medium' },
        ],
      },
      jungikliai: {
        symbols: [
          { x_pct: 0.4, y_pct: 0.5, confidence: 'high' },
        ],
      },
    },
  };

  assert.deepEqual(getConfirmableSymbolCounts(result), {
    sviestuvai: 2,
    jungikliai: 1,
  });
});

test('removeSymbolPoint: removes the clicked filtered point from a template result', () => {
  const result = {
    symbol_type: 'template_symbol',
    matches: [
      { x_pct: 0.1, y_pct: 0.2, confidence: 'high' },
      { x_pct: 0.3, y_pct: 0.4, confidence: 'medium' },
    ],
  };

  assert.deepEqual(removeSymbolPoint(result, 1), {
    symbol_type: 'template_symbol',
    matches: [
      { x_pct: 0.1, y_pct: 0.2, confidence: 'high' },
    ],
    count: 1,
  });
});

test('removeSymbolPoint: removes the clicked filtered point from bundled results', () => {
  const result = {
    symbol_type: 'page_scan',
    by_type: {
      sviestuvai: { count: 2, symbols: [
        { x_pct: 0.2, y_pct: 0.3, confidence: 'high' },
        { x_pct: 0.4, y_pct: 0.5, confidence: 'medium' },
      ] },
      jungikliai: { count: 1, symbols: [
        { x_pct: 0.6, y_pct: 0.7, confidence: 'high' },
      ] },
    },
  };

  assert.deepEqual(removeSymbolPoint(result, 1), {
    symbol_type: 'page_scan',
    by_type: {
      sviestuvai: { count: 1, symbols: [
        { x_pct: 0.2, y_pct: 0.3, confidence: 'high' },
      ] },
      jungikliai: { count: 1, symbols: [
        { x_pct: 0.6, y_pct: 0.7, confidence: 'high' },
      ] },
    },
    count: 2,
  });
});
