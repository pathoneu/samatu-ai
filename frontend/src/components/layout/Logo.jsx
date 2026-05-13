import React from 'react';

/**
 * Logo — north arrow mark + wordmark.
 *
 * Aesthetic 2026-05-12: replaced the abstract "S" tile with a north
 * arrow drawn in LT brėžinių stiliumi. Matches the landing page nav
 * and the floor plan SVG inside the hero.
 */
export default function Logo({ size = 'md', showSub = true, showVersion = false }) {
  const sizes = {
    sm: { icon: 18, text: 'text-sm', sub: 'text-[10px]', ver: 'text-[10px]' },
    md: { icon: 22, text: 'text-base', sub: 'text-xs', ver: 'text-[11px]' },
    lg: { icon: 28, text: 'text-lg', sub: 'text-sm', ver: 'text-xs' },
  };
  const s = sizes[size] || sizes.md;

  return (
    <div className="flex items-center gap-2.5 text-foreground">
      <NorthArrow size={s.icon} />
      <div className="flex flex-col">
        <span className={`${s.text} font-semibold tracking-tight leading-none flex items-center gap-2`}>
          Sąmatų AI
          {showVersion && (
            <span className={`${s.ver} font-mono text-muted-foreground font-normal`}>
              v0.4 — beta
            </span>
          )}
        </span>
        {showSub && (
          <span className={`${s.sub} text-muted-foreground leading-none mt-1`}>
            Statybų sąmatos iš brėžinių
          </span>
        )}
      </div>
    </div>
  );
}

function NorthArrow({ size = 22 }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.1"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <circle cx="12" cy="12" r="10.5" strokeOpacity="0.4" />
      <path d="M12 4 L8.5 17 L12 14 L15.5 17 Z" fill="currentColor" />
      <text
        x="12"
        y="3"
        textAnchor="middle"
        fontSize="3.4"
        fontFamily="JetBrains Mono, monospace"
        fill="currentColor"
        stroke="none"
      >
        Š
      </text>
    </svg>
  );
}
