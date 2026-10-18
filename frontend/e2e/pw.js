/**
 * The Playwright test API, resolved from the runner that is running this file.
 *
 * Playwright is not a dependency of this app (same decision as scripts/og-shot.mjs and
 * scripts/prerender-driver.mjs): `npm run test:e2e` runs the pinned runner through
 * `npm exec --package=playwright@1.55.1`, which only prepends the staged package's
 * node_modules/.bin to PATH — it does not make `import 'playwright/test'` resolvable from
 * this folder. So the spec imports `test` / `expect` from here: the same file the runner
 * itself loaded, found through that PATH entry (one module instance — two copies of
 * playwright/test make every test() call fail with "did not expect test() to be called").
 */
import { createRequire } from 'node:module';
import path from 'node:path';

function loadPlaywrightTest() {
  // Direct resolution first — works if @playwright/test ever becomes a real devDependency.
  for (const id of ['@playwright/test', 'playwright/test']) {
    try {
      return createRequire(import.meta.url)(id);
    } catch {
      /* expected: not a project dependency */
    }
  }
  for (const bin of (process.env.PATH ?? '').split(path.delimiter)) {
    if (!bin.endsWith(path.join('node_modules', '.bin'))) continue;
    try {
      return createRequire(path.join(bin, '..', 'probe.js'))('playwright/test');
    } catch {
      /* not this entry */
    }
  }
  throw new Error(
    'playwright/test not found. Run the suite with `npm run test:e2e` (it goes through '
    + '`npm exec --package=playwright@1.55.1`); first run on a new machine: '
    + '`npx -y playwright@1.55.1 install chromium`.',
  );
}

const pw = loadPlaywrightTest();
export const test = pw.test;
export const expect = pw.expect;
export const defineConfig = pw.defineConfig;
export const devices = pw.devices;
