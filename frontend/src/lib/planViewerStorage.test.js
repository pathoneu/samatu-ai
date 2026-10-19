/**
 * The legacy viewer (`?viewer=legacy`, components/project/PlanViewer.jsx) reads storage only through
 * lib/browserStorage (B2-B item 7): Safari with „Block all cookies" throws on the mere `window.localStorage`
 * read, which crashed the workspace into the error screen (B1-A). Comments may still name it; code may not.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const src = readFileSync(new URL('../components/project/PlanViewer.jsx', import.meta.url), 'utf8');
// strip block and line comments (JSX comments are block comments inside braces)
const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');

test('PlanViewer reads storage only through browserStorage()', () => {
  assert.doesNotMatch(code, /\blocalStorage\b/, 'a bare localStorage read is back in PlanViewer.jsx');
  assert.doesNotMatch(code, /\bsessionStorage\b/);
  assert.match(code, /import \{ browserStorage \} from '@\/lib\/browserStorage'/);
});
