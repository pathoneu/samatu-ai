/**
 * Founder-guide smoke suite (Pathon v3 wave 0). Runs against servers that are ALREADY up — it starts
 * nothing. See founder-guide.spec.js for the two commands and docs/DEVELOPING.md › „E2E smoke".
 *
 * A plain object, not defineConfig(): Playwright is not a dependency of this app (see pw.js).
 */
export default {
  testDir: '.',
  testMatch: /(founder-guide|workspace-frame|room-click|click-model|measure-rows|market-readiness|legend-ui|guidance|viewer-chrome|edit-gestures|patikra-in-place|safari-robustness)\.spec\.js$/,
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
  // chromium runs everything; webkit (Safari's engine) runs a smoke subset so a Safari-only regression is caught
  // (B1-A, 2026-10-19). One-time install: npm exec --yes --package=playwright@1.55.1 -- playwright install webkit
  // Only one engine: --project=chromium or --project=webkit.
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    {
      name: 'webkit',
      use: { browserName: 'webkit' },
      testMatch: /(founder-guide|workspace-frame|safari-robustness)\.spec\.js$/,
      // founder-guide: tests 1–3 only (coach marks, sheet rail, Perskaityti iš naujo)
      grepInvert: /4 Masteliai|5 room tools|6 measure tools|7 Rasti panašius|8 right panel|9 Palyginti|10 after 04|Versijos|Sąmata: Eksportuoti/,
    },
  ],
};
