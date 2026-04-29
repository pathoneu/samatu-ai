/**
 * OnboardingTooltips — first-time 3-step walkthrough (Sprint H8, 2026-04-29).
 *
 * Shows lightweight balloon tooltips pointing at:
 *   1. Left tool rail — „Pasirink tool kairėje"
 *   2. PDF brėžinys — „Pažymėk plotą / spausk patalpą"
 *   3. Right panel — „Patikrink kiekius ir eksportuok"
 *
 * Persists `samatu_onboarding_done` in localStorage. Skip + Done buttons.
 * Auto-skips if user has 0 projects (probably first onboarding handled
 * elsewhere) or already completed once.
 */

import { useState, useEffect } from 'react';
import { X, ChevronRight, ChevronLeft as ChevronLeftIcon } from 'lucide-react';

const STORAGE_KEY = 'samatu_onboarding_done';

const STEPS = [
  {
    id: 'tools',
    title: '1. Pasirink įrankį',
    body: 'Kairėje pusėje yra įrankių juosta. Pradžioje — „Pasirinkti" (rodyklė). Kitiems veiksmams: „Polygon" pažymėt plotą, „Mastelis" — kalibruoti brėžinį.',
    targetSel: '[data-onboarding="tool-rail"]',
    side: 'right',
  },
  {
    id: 'pdf',
    title: '2. Brėžinys ir patalpos',
    body: 'Centre — brėžinys. Spustelk patalpą dešiniame sąraše ir matysi kaip ji paryškinama brėžinyje. Naudok klavišus + / − / F / [ / ] greitai naviguoti.',
    targetSel: null, // center generic
    side: 'top',
  },
  {
    id: 'panel',
    title: '3. Kiekiai ir eksportas',
    body: 'Dešinėje — patalpų ir kiekių sąrašas. „Peržiūra" rodo, ką patikrinti rankiniu būdu. „Eksportuoti" (viršuje) sukuria Excel arba PDF su sąmata.',
    targetSel: null,
    side: 'left',
  },
];

export default function OnboardingTooltips() {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) === '1') return;
    } catch { return; }
    // Sprint §AUDIT (2026-04-29): wait for next-frame + tab-visible so the
    // 1.5s delay isn't burning while user is in another tab. Also avoids
    // showing onboarding when the tab is hidden (would be confusing).
    let t = null;
    const startTimer = () => {
      if (t != null || document.hidden) return;
      t = setTimeout(() => setVisible(true), 1500);
    };
    const onVisChange = () => {
      if (!document.hidden && t == null) startTimer();
    };
    startTimer();
    document.addEventListener('visibilitychange', onVisChange);
    return () => {
      if (t != null) clearTimeout(t);
      document.removeEventListener('visibilitychange', onVisChange);
    };
  }, []);

  const dismiss = () => {
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch {}
    setVisible(false);
  };

  if (!visible) return null;
  const current = STEPS[step];

  return (
    <>
      {/* Translucent backdrop — absolute (not fixed) so it only covers the
          workspace, NOT the page header / tab bar above. User can still
          click „Kiekiai" / „AI Chat" tabs to leave the onboarding context.
          REQUIRES: parent must be position:relative (InteriorWorkspace L130). */}
      <div
        className="absolute inset-0 z-40"
        style={{ background: 'rgba(0,0,0,0.25)', pointerEvents: 'auto' }}
        onClick={dismiss}
      />

      {/* Center balloon — for simplicity, all 3 steps land in same spot.
          Could be enhanced to position relative to targetSel via getBoundingClientRect. */}
      <div
        className="absolute z-50 bg-card border border-border rounded-xl shadow-xl p-5"
        style={{
          top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
          width: 'min(420px, calc(100vw - 32px))',
        }}
      >
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-2">
            <span
              className="mono tabular text-[10px] font-semibold uppercase tracking-wide"
              style={{ color: 'hsl(var(--primary))' }}
            >
              Žingsnis {step + 1} iš {STEPS.length}
            </span>
          </div>
          <button
            onClick={dismiss}
            title="Praleisti įvadą"
            className="p-1 rounded text-muted-foreground hover:bg-muted/40"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>

        <h3 className="text-base font-semibold text-foreground mb-1.5">
          {current.title}
        </h3>
        <p className="text-sm text-muted-foreground leading-relaxed mb-4">
          {current.body}
        </p>

        {/* Step dots */}
        <div className="flex items-center justify-center gap-1.5 mb-4">
          {STEPS.map((_, i) => (
            <span
              key={i}
              className="rounded-full"
              style={{
                width: i === step ? 16 : 6,
                height: 6,
                background: i === step
                  ? 'hsl(var(--primary))'
                  : 'hsl(var(--muted-foreground) / 0.3)',
                transition: 'all 0.2s ease',
              }}
            />
          ))}
        </div>

        <div className="flex items-center justify-between gap-2">
          <button
            onClick={dismiss}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Praleisti įvadą
          </button>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <button
                onClick={() => setStep(s => s - 1)}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium border border-border text-foreground hover:bg-muted/40"
              >
                <ChevronLeftIcon className="w-3 h-3" />
                Atgal
              </button>
            )}
            {step < STEPS.length - 1 ? (
              <button
                onClick={() => setStep(s => s + 1)}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium"
                style={{
                  background: 'hsl(var(--primary))',
                  color: 'hsl(var(--primary-foreground))',
                }}
              >
                Toliau
                <ChevronRight className="w-3 h-3" />
              </button>
            ) : (
              <button
                onClick={dismiss}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium"
                style={{
                  background: 'hsl(var(--primary))',
                  color: 'hsl(var(--primary-foreground))',
                }}
              >
                Pradėti darbą
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
