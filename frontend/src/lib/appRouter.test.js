/**
 * The app's router contract on react-router 7 (Round 17, 2026-10-05).
 *
 * Facts this guards:
 *  - the app depends on `react-router` 7.18+ and nothing else: v7 folded
 *    `react-router-dom` into it (the old name is only a re-export shim, and v8
 *    drops it), so every import says 'react-router'. A stale 'react-router-dom'
 *    import fails the build without saying which file — this test names it;
 *  - the routes in App.jsx send the same URLs to the same pages as on v6
 *    (checked against 6.30.6 during the upgrade): params decoded, a trailing
 *    slash and letter case ignored, anything unknown → the 404 page;
 *  - 7.18 is the first release that reads a backslash as a slash when it
 *    resolves a link target (GHSA-wrjc-x8rr-h8h6, open redirect): `/\host`
 *    stays on this site instead of becoming the external `//host`;
 *  - the router does not wrap navigations in React.startTransition (v7's
 *    default), so a click on a page whose code is still loading shows
 *    „Kraunama…" at once, as on v6 — see the comment on <Router> in App.jsx.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative } from 'node:path';
import { matchRoutes, resolvePath } from 'react-router';

const HERE = fileURLToPath(import.meta.url);
const SRC = join(dirname(HERE), '..');
const FRONTEND = join(SRC, '..');
const readJson = (p) => JSON.parse(readFileSync(p, 'utf8'));

// "^7.18.4" / "7.18.4" → [7, 18, 4]
const versionParts = (v) => v.replace(/^[\^~]/, '').split('.').map(Number);

test('the app depends on react-router 7.18+ and no longer on react-router-dom', () => {
  const pkg = readJson(join(FRONTEND, 'package.json'));
  const deps = { ...pkg.dependencies, ...pkg.devDependencies };
  assert.equal(deps['react-router-dom'], undefined, 'react-router-dom is still listed in package.json');
  assert.ok(deps['react-router'], 'react-router is missing from package.json');
  const [major, minor] = versionParts(deps['react-router']);
  assert.equal(major, 7, `package.json asks for react-router ${deps['react-router']}`);
  assert.ok(minor >= 18, `package.json allows react-router ${deps['react-router']}, below the 7.18 security fix`);

  // The lockfile is what CI and the deploy install.
  const lock = readJson(join(FRONTEND, 'package-lock.json')).packages;
  assert.equal(lock['node_modules/react-router-dom'], undefined, 'package-lock.json still installs react-router-dom');
  const [lockMajor, lockMinor] = versionParts(lock['node_modules/react-router'].version);
  assert.ok(lockMajor === 7 && lockMinor >= 18,
    `package-lock.json pins react-router ${lock['node_modules/react-router'].version}`);
});

test("every router import in src names 'react-router'", () => {
  const stale = /(?:\bfrom\s*|\bimport\s*\(\s*|\brequire\s*\(\s*)['"]react-router-dom(?:\/[^'"]*)?['"]/;
  const found = [];
  let importers = 0;
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const p = join(dir, entry.name);
      if (entry.isDirectory()) { walk(p); continue; }
      if (!/\.(m?js|jsx)$/.test(entry.name) || p === HERE) continue;
      const text = readFileSync(p, 'utf8');
      if (stale.test(text)) found.push(relative(FRONTEND, p));
      if (/\bfrom\s*['"]react-router['"]/.test(text)) importers += 1;
    }
  };
  walk(SRC);
  assert.deepEqual(found, [], `still importing react-router-dom: ${found.join(', ')}`);
  assert.ok(importers > 0, 'no file imports react-router — the scan is looking in the wrong place');
});

// The paths straight from App.jsx — the protected pages sit under one pathless
// layout route (AppLayout), so a flat list matches exactly as the real tree does.
const appPaths = () => {
  const app = readFileSync(join(SRC, 'App.jsx'), 'utf8');
  return [...app.matchAll(/<Route\s+path="([^"]+)"/g)].map((m) => m[1]);
};

test('App.jsx routes send each URL to the same page as before the upgrade', () => {
  const paths = appPaths();
  const routes = paths.map((path) => ({ path }));
  const cases = [
    ['/', '/'],
    ['/dashboard', '/dashboard'],
    ['/dashboard/', '/dashboard'],
    ['/Dashboard', '/dashboard'],
    ['/en', '/en'],
    ['/login', '/login'],
    ['/settings', '/settings'],
    ['/admin', '/admin'],
    ['/billing/success', '/billing/success'],
    ['/project/abc', '/project/:id', { id: 'abc' }],
    ['/project/a%20b', '/project/:id', { id: 'a b' }],
    ['/project/abc/patikra', '/project/:id/patikra', { id: 'abc' }],
    ['/share/t0k', '/share/:token', { token: 't0k' }],
    ['/project', '*'],
    ['/no/such/page', '*'],
  ];
  for (const [url, expected, params] of cases) {
    assert.ok(paths.includes(expected), `App.jsx no longer has a route "${expected}"`);
    const matches = matchRoutes(routes, url);
    const leaf = matches?.[matches.length - 1];
    assert.equal(leaf?.route.path, expected, `${url} opened ${leaf?.route.path}, not ${expected}`);
    if (params) {
      for (const [k, v] of Object.entries(params)) assert.equal(leaf.params[k], v, `${url}: param ${k}`);
    }
  }
});

test('a click shows the loading screen at once (router transitions off)', () => {
  const app = readFileSync(join(SRC, 'App.jsx'), 'utf8');
  const router = app.match(/<Router\b[^>]*>/);
  assert.ok(router, 'App.jsx has no <Router> element');
  assert.match(router[0], /\buseTransitions=\{false\}/,
    'v7 would keep the old page on screen, with no sign the click registered, until the new page loads');
});

test('a backslash in a link target cannot take the user off the site (7.18+)', () => {
  // Browsers read "\" as "/" in a URL, so `/\host` used to resolve to the
  // protocol-relative `//host` — another site.
  assert.equal(resolvePath('/\\evil.example').pathname, '/evil.example');
  assert.equal(resolvePath('\\\\evil.example').pathname, '/evil.example');
  assert.equal(resolvePath('//evil.example').pathname, '/evil.example');
  // The app's own targets are unchanged.
  assert.deepEqual(resolvePath('/project/abc?step=samata'),
    { pathname: '/project/abc', search: '?step=samata', hash: '' });
});
