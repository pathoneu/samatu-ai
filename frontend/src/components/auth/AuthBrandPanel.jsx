/**
 * AuthBrandPanel — the branded right-hand column on the Login / Register
 * pages (2026-07-05 dark graphite identity).
 *
 * Renders a deep-graphite panel with the blueprint hairline grid + a faint
 * orange radial glow (the landing motif) and a small "AI aptinka kiekius"
 * detection illustration: a floor-plan grid with orange detection boxes +
 * mono quantity labels. Hidden on mobile (< lg) — the auth form stands
 * alone on small screens.
 *
 * Pure presentation, no state. `headline` may be a string or JSX (so the
 * caller can wrap a noun in <span className="h-accent">).
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { PathonMark } from '@/components/layout/Logo';

// Room NAME localised via i18n key; the quantity string stays literal so the
// LT panel renders identically to the founder-approved copy.
const DEMO_ROOMS = [
  { key: 'svetaine', v: '28,4 m²' },
  { key: 'miegamasis', v: '14,2 m²' },
  { key: 'vonia', v: '4,6 m²' },
];

export default function AuthBrandPanel({ eyebrow, headline, sub }) {
  const { t } = useTranslation();
  return (
    <div className="relative hidden lg:flex flex-col justify-between overflow-hidden border-l border-border bg-card p-14">
      {/* blueprint grid + orange glow motif */}
      <div className="blueprint-grid-major absolute inset-0 pointer-events-none" aria-hidden />
      <div
        className="absolute -right-24 -top-24 h-[420px] w-[420px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, hsl(var(--primary) / 0.16), transparent 68%)' }}
        aria-hidden
      />

      {/* top: mark + eyebrow */}
      <div className="relative flex items-center gap-2.5 text-foreground">
        <PathonMark icon={26} />
        <span className="mono-tick">{eyebrow}</span>
      </div>

      {/* middle: detection illustration */}
      <div className="relative my-10">
        <div className="product-frame p-4">
          <svg viewBox="0 0 370 200" className="w-full" role="img" aria-label={t('landing.heroPlan.title')}>
            <defs>
              <pattern id="authGrid" width="24" height="24" patternUnits="userSpaceOnUse">
                <path d="M24 0H0V24" fill="none" stroke="hsl(var(--foreground) / 0.06)" strokeWidth="1" />
              </pattern>
            </defs>
            <rect x="0" y="0" width="370" height="200" fill="url(#authGrid)" rx="6" />

            {/* plan outline */}
            <rect x="8" y="8" width="354" height="184" fill="none"
              stroke="hsl(var(--foreground) / 0.16)" strokeWidth="1.4" rx="3" />
            <line x1="150" y1="8" x2="150" y2="120" stroke="hsl(var(--foreground) / 0.16)" strokeWidth="1.4" />
            <line x1="8" y1="120" x2="362" y2="120" stroke="hsl(var(--foreground) / 0.16)" strokeWidth="1.4" />
            <line x1="256" y1="120" x2="256" y2="192" stroke="hsl(var(--foreground) / 0.16)" strokeWidth="1.4" />

            {/* detection boxes */}
            {[
              { x: 20, y: 20, w: 118, h: 88, roomKey: 'svetaine', val: '28,4 m²' },
              { x: 164, y: 20, w: 184, h: 88, roomKey: 'miegamasis', val: '14,2 m²' },
              { x: 20, y: 132, w: 222, h: 48, roomKey: 'koridorius', val: '10,9 m²' },
              { x: 270, y: 132, w: 78, h: 48, roomKey: 'vonia', val: '4,6 m²' },
            ].map((b, i) => (
              <g key={i}>
                <rect x={b.x} y={b.y} width={b.w} height={b.h}
                  fill="hsl(var(--primary) / 0.07)"
                  stroke="hsl(var(--primary))" strokeWidth="1.4" rx="2" />
                {/* corner brackets */}
                {[
                  [b.x, b.y, 1, 1], [b.x + b.w, b.y, -1, 1],
                  [b.x, b.y + b.h, 1, -1], [b.x + b.w, b.y + b.h, -1, -1],
                ].map(([cx, cy, dx, dy], j) => (
                  <path key={j}
                    d={`M ${cx + dx * 8} ${cy} H ${cx} V ${cy + dy * 8}`}
                    fill="none" stroke="hsl(var(--primary))" strokeWidth="1.8" />
                ))}
                <text x={b.x + 7} y={b.y + 18}
                  fontFamily="var(--font-mono)" fontSize="9" fontWeight="600"
                  fill="hsl(var(--foreground))">{t(`landing.heroRooms.${b.roomKey}`)}</text>
                <text x={b.x + 7} y={b.y + 31}
                  fontFamily="var(--font-mono)" fontSize="9"
                  fill="hsl(var(--primary))">{b.val}</text>
              </g>
            ))}
          </svg>
        </div>

        {/* extracted-quantity ticker under the frame */}
        <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1.5">
          {DEMO_ROOMS.map((r) => (
            <div key={r.key} className="flex items-center gap-1.5 text-xs">
              <span className="dot dot-table" />
              <span className="text-muted-foreground">{t(`landing.heroRooms.${r.key}`)}</span>
              <span className="mono tabular text-foreground">{r.v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* bottom: headline + sub */}
      <div className="relative">
        <h2 className="font-display text-2xl font-semibold tracking-tight leading-snug text-foreground max-w-md">
          {headline}
        </h2>
        {sub && (
          <p className="mt-3 text-sm text-muted-foreground max-w-md leading-relaxed">
            {sub}
          </p>
        )}
      </div>
    </div>
  );
}
