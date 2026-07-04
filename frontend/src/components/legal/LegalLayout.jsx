/**
 * LegalLayout — shared dark-graphite chrome for legal long-form pages
 * (Privatumo politika / Slapukų politika / Naudojimo sąlygos).
 *
 * Matches the Pathon dark identity (2026-07-05): graphite surfaces, orange
 * accent, blueprint-grid hero band, Sora display headings, JetBrains Mono
 * eyebrows + section numbers, Hanken Grotesk body. Readable long-form:
 * a single prose column capped at ~68ch, generous vertical rhythm,
 * muted-foreground body ink.
 *
 * The three legal pages compose their content inside <LegalLayout>, and use
 * the exported <Section>, <P>, <UL>/<LI>, <Callout>, <DefRow> primitives so
 * the typographic scale stays identical across all three.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { PathonMark } from '@/components/layout/Logo';

// ─── Page shell ──────────────────────────────────────────────────────

export default function LegalLayout({
  eyebrow,       // mono eyebrow (e.g. "Teisė / Privatumas")
  index,         // mono coordinate index (e.g. "LEX-01")
  title,         // page title (Sora display)
  intro,         // one-line lede under the title
  updated,       // last-updated date string
  effective,     // effective date string (optional)
  children,      // page body — <Section>…</Section> blocks
}) {
  return (
    <div className="pathon-landing min-h-screen bg-background text-foreground antialiased">
      {/* Lite header — logo home + back link, matches landing nav rhythm */}
      <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-md supports-[backdrop-filter]:bg-background/70">
        <div className="max-w-[1200px] mx-auto px-5 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 text-foreground">
            <PathonMark icon={26} />
            <span className="font-display font-bold tracking-tight text-[19px]">Pathon</span>
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-[13.5px] text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Grįžti į pradžią
          </Link>
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
            <h1 className="mt-6 font-display font-bold text-foreground tracking-[-0.03em] leading-[1.0] text-[38px] sm:text-[54px]">
              {title}
            </h1>
            {intro && (
              <p className="mt-6 max-w-[620px] text-[16.5px] sm:text-[18px] text-ink-2 leading-[1.6]">
                {intro}
              </p>
            )}
            <div className="mt-7 flex flex-wrap items-center gap-x-4 gap-y-1.5 font-mono text-[11.5px] text-muted-foreground">
              {updated && <span>Atnaujinta: {updated}</span>}
              {effective && (
                <>
                  <span className="text-border-strong hidden sm:inline">·</span>
                  <span>Įsigalioja: {effective}</span>
                </>
              )}
            </div>

            {/* Draft notice — legally load-bearing disclaimer */}
            <div className="mt-8 flex items-start gap-3 rounded-xl border border-primary/30 bg-primary/[0.07] px-4 py-3.5">
              <span
                className="mt-[3px] shrink-0 w-2 h-2 rounded-full bg-primary"
                aria-hidden
              />
              <p className="text-[13.5px] text-ink-2 leading-[1.55]">
                Ši politika — projektas, kurį prieš publikavimą turi peržiūrėti
                teisininkas.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Prose column — capped at readable measure */}
      <main className="relative max-w-[1200px] mx-auto px-5 lg:px-8 py-16 lg:py-20">
        <article className="legal-prose max-w-[68ch]">{children}</article>

        {/* Footer nav between the three legal pages */}
        <nav className="max-w-[68ch] mt-16 pt-8 border-t border-border flex flex-wrap items-center gap-x-6 gap-y-3 text-[13.5px]">
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Teisiniai dokumentai
          </span>
          <Link to="/privacy" className="text-foreground/75 hover:text-foreground transition-colors link-draw">
            Privatumo politika
          </Link>
          <Link to="/cookies" className="text-foreground/75 hover:text-foreground transition-colors link-draw">
            Slapukų politika
          </Link>
          <Link to="/terms" className="text-foreground/75 hover:text-foreground transition-colors link-draw">
            Naudojimo sąlygos
          </Link>
        </nav>

        <p className="max-w-[68ch] mt-8 text-[12.5px] text-muted-foreground leading-[1.6]">
          © 2026 Pathon, MB · <a href="mailto:solutions@pathon.eu" className="hover:text-foreground transition-colors">solutions@pathon.eu</a>
        </p>
      </main>
    </div>
  );
}

// ─── Prose primitives ────────────────────────────────────────────────
// Hand-styled (the project has no @tailwindcss/typography plugin, so the
// old `prose` classes were inert). These give the three pages one shared,
// deliberate typographic scale.

/** A numbered top-level section: mono number + Sora heading + body. */
export function Section({ n, title, id, children }) {
  return (
    <section id={id} className="mt-12 first:mt-0 scroll-mt-24">
      <div className="flex items-baseline gap-3">
        {n != null && (
          <span className="font-mono text-[12px] text-primary tracking-[0.08em] tabular pt-1 shrink-0">
            {String(n).padStart(2, '0')}
          </span>
        )}
        <h2 className="font-display font-semibold text-foreground tracking-[-0.015em] leading-[1.15] text-[22px] sm:text-[26px]">
          {title}
        </h2>
      </div>
      <div className="mt-4 sm:pl-[calc(0.75rem+2.4ch)] space-y-4">{children}</div>
    </section>
  );
}

/** A sub-heading inside a section. */
export function SubHead({ children }) {
  return (
    <h3 className="mt-6 mb-1 font-display font-semibold text-foreground text-[16px] tracking-[-0.01em]">
      {children}
    </h3>
  );
}

/** Body paragraph — muted, readable measure, comfortable leading. */
export function P({ children, className = '' }) {
  return (
    <p className={`text-[15px] text-ink-2 leading-[1.68] ${className}`}>
      {children}
    </p>
  );
}

/** Emphasised inline term. */
export function Term({ children }) {
  return <strong className="text-foreground font-semibold">{children}</strong>;
}

/** Bulleted list with orange tick markers. */
export function UL({ children, className = '' }) {
  return <ul className={`space-y-2.5 ${className}`}>{children}</ul>;
}

export function LI({ children }) {
  return (
    <li className="flex items-start gap-2.5 text-[15px] text-ink-2 leading-[1.6]">
      <span
        className="mt-[9px] shrink-0 w-1.5 h-1.5 rounded-full bg-primary/70"
        aria-hidden
      />
      <span className="min-w-0">{children}</span>
    </li>
  );
}

/** Nested sub-list (no top margin, indented). */
export function SubUL({ children }) {
  return <ul className="mt-2 ml-1 space-y-1.5">{children}</ul>;
}

export function SubLI({ children }) {
  return (
    <li className="flex items-start gap-2 text-[14px] text-muted-foreground leading-[1.55]">
      <span className="mt-[8px] shrink-0 w-1 h-1 rounded-full bg-muted-foreground/70" aria-hidden />
      <span className="min-w-0">{children}</span>
    </li>
  );
}

/** Highlighted callout box (critical clauses — orange left rule). */
export function Callout({ title, children, tone = 'primary' }) {
  const border =
    tone === 'primary' ? 'border-primary/35 bg-primary/[0.06]' : 'border-border bg-card';
  return (
    <div className={`mt-5 rounded-xl border ${border} p-5`}>
      {title && (
        <div className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-primary mb-2.5">
          {title}
        </div>
      )}
      <div className="space-y-3">{children}</div>
    </div>
  );
}

/** Inline code / cookie name / field name. */
export function Code({ children }) {
  return (
    <code className="font-mono text-[13px] px-1.5 py-0.5 rounded bg-surface-2 border border-border text-foreground/90">
      {children}
    </code>
  );
}

/** TODO placeholder — visibly flags a value the founder must fill in. */
export function Todo({ children }) {
  return (
    <span
      className="inline-flex items-center gap-1 font-mono text-[12px] px-1.5 py-0.5 rounded border border-primary/40 bg-primary/[0.08] text-primary align-baseline"
      title="Užpildyti prieš publikuojant"
    >
      {children}
    </span>
  );
}

/** Definition table (e.g. cookie schedule) — dark, mono cells, scrolls on
 *  narrow viewports so the page body never scrolls horizontally. */
export function DefTable({ head, rows }) {
  return (
    <div className="mt-4 -mx-1 overflow-x-auto">
      <table className="w-full min-w-[520px] border-collapse text-left">
        <thead>
          <tr className="border-b border-border-strong">
            {head.map((h) => (
              <th
                key={h}
                className="py-2.5 pr-4 font-mono text-[10.5px] uppercase tracking-[0.1em] text-muted-foreground font-semibold align-bottom"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border/70 align-top">
              {r.map((cell, j) => (
                <td
                  key={j}
                  className={`py-3 pr-4 text-[13.5px] leading-[1.5] ${
                    j === 0 ? 'font-mono text-foreground/90 whitespace-nowrap' : 'text-ink-2'
                  }`}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
