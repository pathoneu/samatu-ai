/**
 * Pagalba — a short help page and „Kas naujo" (v3 W7-A M6, 2026-10-18).
 *
 * Text lives in lib/helpContent.js. Nordic Slate tokens only; no new fonts.
 * „Rodyti įvadą dar kartą" clears the viewer walkthrough's done-flag so the next
 * opened drawing shows it again.
 */
import React, { useState } from 'react';
import { Link } from 'react-router';
import { LifeBuoy, Sparkles, RotateCcw } from 'lucide-react';
import { HELP_SECTIONS, WHATS_NEW } from '@/lib/helpContent';
import { resetCoachMarks } from '@/lib/viewerCoachMarks';
import { resetFirstUse } from '@/lib/firstUseHints';

export default function Pagalba() {
  const [introReset, setIntroReset] = useState(false);
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-foreground flex items-center gap-2">
          <LifeBuoy className="w-6 h-6 text-primary" aria-hidden />
          Pagalba
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Trumpai: kaip patikrinti skaičių, pataisyti kontūrą ir ką reiškia linijos brėžinyje.
          Klausimą galite parašyti adresu{' '}
          <a href="mailto:solutions@pathon.eu" className="underline text-foreground">solutions@pathon.eu</a>.
        </p>
        <nav aria-label="Turinys" className="mt-4 flex flex-wrap gap-2">
          {HELP_SECTIONS.map((s) => (
            <a key={s.id} href={`#${s.id}`}
              className="text-sm px-2.5 py-1 rounded-[2px] border border-border bg-card hover:bg-muted text-foreground no-underline">
              {s.title}
            </a>
          ))}
          <a href="#kas-naujo"
            className="text-sm px-2.5 py-1 rounded-[2px] border border-border bg-card hover:bg-muted text-foreground no-underline">
            Kas naujo
          </a>
        </nav>
      </header>

      <div className="space-y-6">
        {HELP_SECTIONS.map((s) => (
          <section key={s.id} id={s.id} className="rounded-[4px] border border-border bg-card p-5">
            <h2 className="text-base font-semibold text-foreground mb-3">{s.title}</h2>
            <ol className="list-decimal pl-5 space-y-2 text-sm text-foreground leading-relaxed">
              {s.steps.map((step) => <li key={step}>{step}</li>)}
            </ol>
          </section>
        ))}

        <section className="rounded-[4px] border border-border bg-card p-5">
          <h2 className="text-base font-semibold text-foreground mb-2">Įvadas brėžinyje</h2>
          <p className="text-sm text-muted-foreground">
            Pirmą kartą atidarius brėžinį trumpi patarimai rodomi po vieną — prie to, ką jie paaiškina.
          </p>
          <button type="button"
            onClick={() => { resetCoachMarks(); resetFirstUse(); setIntroReset(true); }}
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[2px] border border-border text-sm hover:bg-muted"
            data-testid="help-reset-intro">
            <RotateCcw className="w-4 h-4" aria-hidden /> Rodyti įvadą dar kartą
          </button>
          {introReset && (
            <p role="status" className="mt-2 text-sm text-foreground">
              Gerai — įvadas bus parodytas kitą kartą atidarius brėžinį.{' '}
              <Link to="/" className="underline">Į projektus</Link>
            </p>
          )}
        </section>

        <section id="kas-naujo" className="rounded-[4px] border border-border bg-card p-5">
          <h2 className="text-base font-semibold text-foreground mb-3 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-primary" aria-hidden /> Kas naujo
          </h2>
          <div className="space-y-4">
            {WHATS_NEW.map((r) => (
              <div key={r.date}>
                <p className="text-sm font-semibold text-foreground tabular-nums">{r.date}</p>
                <ul className="mt-1 list-disc pl-5 space-y-1 text-sm text-foreground leading-relaxed">
                  {r.items.map((it) => <li key={it}>{it}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
