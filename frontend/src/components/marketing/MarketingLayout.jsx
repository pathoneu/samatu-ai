/**
 * MarketingLayout — shared chrome for public BoFu/guide pages
 * (/samatininko-kaina, /kiekiai-is-brezinio, /vidaus-apdailos-samata,
 * /apva-renovacijos-kiekiai — docs/marketing/seo-playbook.md §3).
 *
 * Mirrors LegalLayout's dark-graphite identity 1:1 (same lite header,
 * blueprint hero band, mono eyebrow + index, 68ch prose column) so the
 * public site reads as one system — but drops the legal-only chrome
 * (lawyer draft notice, LT-only body notice, legal doc nav) and adds what
 * a marketing page needs: one CTA band to /register and a related-pages nav.
 *
 * Body content composes the SAME prose primitives exported by LegalLayout
 * (<Section>, <P>, <UL>/<LI>, <Callout>, <DefTable>) — one typographic
 * scale across legal + marketing long-form.
 *
 * SEO: pages call setPageMeta()/setJsonLd() themselves — the <title> and
 * meta description are tuned separately from the visible h1/intro (unlike
 * LegalLayout, which derives meta from its props).
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { PathonMark } from '@/components/layout/Logo';

export default function MarketingLayout({
  eyebrow,       // mono eyebrow (e.g. "Gidas / Kainos")
  index,         // mono coordinate index (e.g. "GID-01")
  title,         // page h1 (Sora display)
  intro,         // one-line lede under the title
  updated,       // last-updated date string (content freshness signal)
  related = [],  // [{ to, label }] — internal links to sibling pages
  ctaTitle = 'Išbandykite su savo brėžiniu',
  ctaText = 'Įkelkite projekto PDF — kiekiai ir sąmatos juodraštis paprastai būna paruošti per 15 minučių. Kainas suvedate patys.',
  children,      // page body — <Section>…</Section> blocks
}) {
  return (
    <div className="pathon-landing min-h-screen bg-background text-foreground antialiased">
      {/* Lite header — logo home + back link, matches landing nav rhythm */}
      <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-md supports-[backdrop-filter]:bg-background/70">
        <div className="max-w-[1200px] mx-auto px-5 lg:px-8 h-16 flex items-center justify-between">
          {/* Home → /about (LT landing), NOT "/" — the root route redirects
              logged-in users to /dashboard. These BoFu pages are LT-only. */}
          <Link to="/about" className="flex items-center gap-2.5 text-foreground">
            <PathonMark icon={26} />
            <span className="font-display font-bold tracking-tight text-[19px]">Pathon</span>
          </Link>
          <div className="flex items-center gap-4">
            <Link
              to="/about"
              className="inline-flex items-center gap-1.5 text-[13.5px] text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="w-4 h-4" /> Grįžti į pradžią
            </Link>
          </div>
        </div>
      </header>

      {/* Hero band — blueprint grid + orange radial glow, page title */}
      <section className="relative border-b border-border overflow-hidden">
        <div className="absolute inset-0 blueprint-grid-major opacity-70 pointer-events-none" aria-hidden />
        <div
          className="absolute -top-52 -right-40 w-[560px] h-[560px] rounded-full pointer-events-none"
          aria-hidden
          style={{ background: 'radial-gradient(circle, hsl(var(--primary) / 0.13), transparent 62%)' }}
        />
        <div className="relative max-w-[1200px] mx-auto px-5 lg:px-8 pt-14 pb-12 lg:pt-20 lg:pb-14">
          <div className="max-w-[760px]">
            <div className="flex items-center gap-2.5">
              {index && <span className="mono-tick">{index}</span>}
              <span className="font-mono text-[11px] tracking-[0.18em] uppercase text-primary">
                {eyebrow}
              </span>
            </div>
            <h1 className="mt-6 font-display font-bold text-foreground tracking-[-0.03em] leading-[1.05] text-[34px] sm:text-[48px]">
              {title}
            </h1>
            {intro && (
              <p className="mt-6 max-w-[620px] text-[16.5px] sm:text-[18px] text-ink-2 leading-[1.6]">
                {intro}
              </p>
            )}
            {updated && (
              <div className="mt-7 font-mono text-[11.5px] text-muted-foreground">
                Atnaujinta: {updated}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Prose column — capped at readable measure */}
      <main className="relative max-w-[1200px] mx-auto px-5 lg:px-8 py-16 lg:py-20">
        <article className="legal-prose max-w-[68ch]">{children}</article>

        {/* The one CTA — registruotis (seo-playbook §3: one CTA per page) */}
        <aside className="max-w-[68ch] mt-16">
          <div className="relative overflow-hidden rounded-2xl border border-primary/30 bg-primary/[0.06] p-7 sm:p-9">
            <div className="absolute inset-0 blueprint-grid-major opacity-40 pointer-events-none" aria-hidden />
            <div className="relative">
              <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-primary mb-3">
                Pathon
              </div>
              <h2 className="font-display font-bold text-foreground tracking-[-0.02em] leading-[1.15] text-[24px] sm:text-[28px]">
                {ctaTitle}
              </h2>
              <p className="mt-3 max-w-[52ch] text-[15px] text-ink-2 leading-[1.6]">
                {ctaText}
              </p>
              <div className="mt-6 flex flex-wrap items-center gap-3">
                <Link to="/register" className="btn-primary px-5 py-2.5 text-[14px]">
                  Registruotis <ArrowRight className="w-4 h-4" />
                </Link>
                <Link to="/duk" className="btn-ghost px-5 py-2.5 text-[14px]">
                  Skaityti DUK
                </Link>
              </div>
              <p className="mt-4 font-mono text-[11px] text-muted-foreground">
                Pirmasis projektas įmonei — nemokamas
              </p>
            </div>
          </div>
        </aside>

        {/* Related public pages — internal link graph */}
        {related.length > 0 && (
          <nav className="max-w-[68ch] mt-14 pt-8 border-t border-border flex flex-wrap items-center gap-x-6 gap-y-3 text-[13.5px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              Susiję puslapiai
            </span>
            {related.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className="text-foreground/75 hover:text-foreground transition-colors link-draw"
              >
                {label}
              </Link>
            ))}
          </nav>
        )}

        <p className="max-w-[68ch] mt-8 text-[12.5px] text-muted-foreground leading-[1.6]">
          © 2026 Pathon, MB ·{' '}
          <a href="mailto:solutions@pathon.eu" className="hover:text-foreground transition-colors">
            solutions@pathon.eu
          </a>
        </p>
      </main>
    </div>
  );
}
