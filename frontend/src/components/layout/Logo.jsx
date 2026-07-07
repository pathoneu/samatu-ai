import React from 'react';

/**
 * Logo — Pathon monogram (geometric P + accent node) + wordmark.
 *
 * Brand 2026-07-05 (dark graphite): the "Monogram P" — a geometric P stem +
 * bowl in `currentColor` (foreground / near-white on dark) with an ORANGE
 * accent node (--primary) where the bowl meets the stem. Wordmark set in
 * font-display (Sora) semibold.
 */
export default function Logo({ size = 'md', showSub = true, showVersion = false }) {
  const sizes = {
    sm: { icon: 20, text: 'text-sm', sub: 'text-[10px]', ver: 'text-[10px]' },
    md: { icon: 24, text: 'text-base', sub: 'text-xs', ver: 'text-[11px]' },
    lg: { icon: 30, text: 'text-lg', sub: 'text-sm', ver: 'text-xs' },
  };
  const s = sizes[size] || sizes.md;

  return (
    <div className="flex items-center gap-2.5 text-foreground">
      <PathonMark icon={s.icon} />
      <div className="flex flex-col">
        <span className={`${s.text} font-display font-semibold tracking-tight leading-none flex items-center gap-2`}>
          Pathon
          {showVersion && (
            <span className={`${s.ver} font-mono text-muted-foreground font-normal tracking-normal`}>
              beta
            </span>
          )}
        </span>
        {showSub && (
          <span className={`${s.sub} text-muted-foreground leading-none mt-1`}>
            Statybų sąmatos iš PDF
          </span>
        )}
      </div>
    </div>
  );
}

export function PathonMark({ icon = 24 }) {
  return (
    <svg viewBox="0 0 32 32" width={icon} height={icon} fill="none" aria-hidden>
      <rect x="7" y="5" width="3.4" height="22" rx="1.5" fill="currentColor" />
      <path d="M10 6.6 H19.5 a6.4 6.4 0 0 1 0 12.8 H10" fill="none"
        stroke="currentColor" strokeWidth="3.4" />
      <circle cx="19.5" cy="13" r="2.4" className="fill-primary" />
    </svg>
  );
}
