/**
 * Founder-guide smoke suite (Pathon v3 wave 0). Runs against servers that are ALREADY up — it starts
 * nothing. See founder-guide.spec.js for the two commands and docs/DEVELOPING.md › „E2E smoke".
 *
 * A plain object, not defineConfig(): Playwright is not a dependency of this app (see pw.js).
 */
export default {
  testDir: '.',
  testMatch: /(founder-guide|workspace-frame|room-click|click-model|market-readiness)\.spec\.js$/,
  outputDir: './.results',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 240_000,
  expect: { timeout: 20_000 },
  globalSetup: './global-setup.js',
  globalTeardown: './global-teardown.js',
  reporter: [['list'], ['./numbers-reporter.js']],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5201',
    viewport: { width: 1440, height: 900 },
    locale: 'lt-LT',
    timezoneId: 'Europe/Vilnius',
    headless: true,
    actionTimeout: 20_000,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
};
