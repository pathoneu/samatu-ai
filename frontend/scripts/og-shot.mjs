/**
 * Regenerate public/og-image.png (1200×630 social-share card).
 *
 * The template is public/og-image.html (brand tokens match Landing: graphite
 * #15181E, orange #F76B1C, mono chips). Re-run after editing the template.
 *
 * @playwright/test is NOT a dependency of this app — use the pinned CLI
 * (browser build is cached in ~/Library/Caches/ms-playwright after first run):
 *
 *   1. npm run dev            # server on :5173 serves public/og-image.html
 *   2. npx -y playwright@1.55.1 screenshot \
 *        --viewport-size="1200,630" --wait-for-timeout=1500 \
 *        http://localhost:5173/og-image.html public/og-image.png
 *
 * (First ever run: npx -y playwright@1.55.1 install chromium)
 */
console.log(
  'Run:\n  npx -y playwright@1.55.1 screenshot --viewport-size="1200,630" ' +
  '--wait-for-timeout=1500 http://localhost:5173/og-image.html public/og-image.png'
);
