/**
 * Sign-in returns to the whole address the visitor asked for — path, query
 * and hash — and never to another site (2026-10-05). See returnPath.js.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { googleSignInPath, isSameSitePath, returnPathFrom } from './returnPath.js';

// What ProtectedRoute puts in state.from: a router location.
const loc = (pathname, search = '', hash = '') => ({ pathname, search, hash, state: null, key: 'k1' });

test('sign-in returns to the path with its query and hash', () => {
  assert.equal(returnPathFrom({ from: loc('/project/x', '?step=samata') }), '/project/x?step=samata');
  assert.equal(
    returnPathFrom({ from: loc('/project/x/patikra', '?kambarys=02', '#a') }),
    '/project/x/patikra?kambarys=02#a',
  );
  assert.equal(returnPathFrom({ from: loc('/dashboard') }), '/dashboard');
  // The browser's address is percent-encoded; it comes back as it was.
  assert.equal(
    returnPathFrom({ from: loc('/project/x/patikra', '?kambarys=1.02&tab=sienos', '#siena%202') }),
    '/project/x/patikra?kambarys=1.02&tab=sienos#siena%202',
  );
});

test('a from given as a plain string is used as it is', () => {
  assert.equal(returnPathFrom({ from: '/project/x?step=samata' }), '/project/x?step=samata');
});

test('no usable from → the start page', () => {
  for (const state of [undefined, null, {}, { from: null }, { from: 42 }, { from: {} }, 'from', []]) {
    assert.equal(returnPathFrom(state), '/', JSON.stringify(state));
  }
});

test('an address off this site → the start page', () => {
  for (const bad of [
    '//evil.example', '///evil.example', '/\\evil.example', '\\\\evil.example',
    'https://evil.example', 'evil.example', 'javascript:alert(1)',
    '/\t/evil.example', '/\n/evil.example', '/a b', '/\u0000', '',
  ]) {
    assert.equal(returnPathFrom({ from: bad }), '/', JSON.stringify(bad));
    assert.equal(isSameSitePath(bad), false, JSON.stringify(bad));
  }
  // Location pieces that join into another site.
  assert.equal(returnPathFrom({ from: loc('//evil.example') }), '/');
  assert.equal(returnPathFrom({ from: loc('/\\evil.example', '?step=samata') }), '/');
});

test('the Google button carries the whole address in next=', () => {
  const href = googleSignInPath('/project/x/patikra?kambarys=02#a');
  assert.ok(href.startsWith('/api/auth/google?next='), href);
  const url = new URL(href, 'https://app.example');
  assert.equal(url.pathname, '/api/auth/google');
  assert.equal(url.searchParams.get('next'), '/project/x/patikra?kambarys=02#a');
  // The query and hash travel INSIDE next: no stray parameter, no own hash.
  assert.deepEqual([...url.searchParams.keys()], ['next']);
  assert.equal(url.hash, '');
});

test('the Google button never sends an address off this site', () => {
  for (const bad of ['//evil.example', 'https://evil.example', '/\\evil.example', undefined, null, 7]) {
    const url = new URL(googleSignInPath(bad), 'https://app.example');
    assert.equal(url.searchParams.get('next'), '/', String(bad));
  }
});

test('Login sends both sign-in paths to the whole address', () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const login = readFileSync(join(here, '..', 'pages', 'Login.jsx'), 'utf8');
  assert.match(login, /const from = returnPathFrom\(location\.state\);/);
  assert.doesNotMatch(login, /from\?\.pathname/, 'Login reads the pathname alone again');
  assert.match(login, /navigate\(from, \{ replace: true \}\)/);
  assert.match(login, /<GoogleSignInButton next=\{from\} \/>/);
  const button = readFileSync(join(here, '..', 'components', 'auth', 'GoogleSignInButton.jsx'), 'utf8');
  assert.match(button, /googleSignInPath\(next\)/);
});
