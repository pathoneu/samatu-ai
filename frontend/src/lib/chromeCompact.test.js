import test from 'node:test';
import assert from 'node:assert/strict';
import { nextChromeCompact, pillNaturalWidth, CHROME_GAP_PX } from './chromeCompact.js';

const OPEN = { compact: false, fullWidth: null };

test('the labelled buttons go icon-only when they no longer fit beside the sheet pill (1280 sąmata split)', () => {
  // measured 2026-10-19: row 361 px, pill 392 px untruncated, labelled card 331 px → it wrapped onto the title
  const s = nextChromeCompact(OPEN, { rowWidth: 361, pillNatural: 392, cardWidth: 331 });
  assert.deepEqual(s, { compact: true, fullWidth: 331 });
  // compact, the card is 116 px: the decision stays (no flicker) until the labelled card fits again
  assert.equal(nextChromeCompact(s, { rowWidth: 428, pillNatural: 392, cardWidth: 116 }), s);
  assert.deepEqual(nextChromeCompact(s, { rowWidth: 392 + CHROME_GAP_PX + 331, pillNatural: 392, cardWidth: 116 }), OPEN);
});

test('a wide drawing keeps the labels; an unmeasured row changes nothing', () => {
  assert.equal(nextChromeCompact(OPEN, { rowWidth: 751, pillNatural: 392, cardWidth: 331 }), OPEN);
  assert.equal(nextChromeCompact(OPEN, { rowWidth: 0, pillNatural: 392, cardWidth: 331 }), OPEN);
});

test('the pill counts its name untruncated, up to the name cap', () => {
  assert.equal(pillNaturalWidth(237, 291, 65), 237 + (220 - 65));
  assert.equal(pillNaturalWidth(200, 120, 120), 200);
  assert.equal(pillNaturalWidth(200, undefined, undefined), 200);
});
