/**
 * SymbolPalette — togal.ai-style symbol placement palette.
 *
 * Each symbol type shows the live count placed on the canvas as a
 * badge ("Rozetė × 14"). Clicking a symbol type activates the
 * place-symbol tool with that type.
 *
 * 2026-06-05: emoji glyphs in the palette replaced with Lucide React
 * icons. The on-canvas rendering still uses unicode glyphs (see
 * SYMBOL_ICONS in AnnotationCanvas) because Fabric.js Text objects
 * can't render React/SVG icons in place — but the palette UI now
 * looks like a real construction tool.
 *
 * Props:
 *   symbols[]    — current symbols (used for count badges)
 *   activeType   — currently-selected symbol type (highlighted)
 *   onSelectType(type) — user clicked a symbol button
 *   onHighlightType(type) — optional: user clicked a count badge to
 *                            highlight all instances on canvas
 */
import React from 'react';
import {
  Power, ToggleLeft, Lightbulb, Wifi, Droplets, Wind,
} from 'lucide-react';
import { SYMBOL_ICONS } from './AnnotationCanvas';

const PALETTE_ICONS = {
  socket:        Power,
  switch:        ToggleLeft,
  light_ceiling: Lightbulb,
  data_outlet:   Wifi,
  water_cold:    Droplets,
  vent_supply:   Wind,
};

// Group the 6 symbol types into 3 categories
const CATEGORIES = [
  {
    label: 'Elektros sistema',
    types: ['socket', 'switch', 'light_ceiling', 'data_outlet'],
  },
  {
    label: 'Santechnika',
    types: ['water_cold'],
  },
  {
    label: 'Vėdinimas / HVAC',
    types: ['vent_supply'],
  },
];

export default function SymbolPalette({
  symbols,
  activeType,
  onSelectType,
  onHighlightType,
}) {
  const counts = (symbols || []).reduce((acc, s) => {
    acc[s.type] = (acc[s.type] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-neutral-200 bg-neutral-50 px-4 py-1.5 text-xs">
      <span className="text-neutral-500">Simboliai:</span>
      {CATEGORIES.map((cat) => (
        <React.Fragment key={cat.label}>
          {cat.types.map((type) => {
            const meta = SYMBOL_ICONS[type];
            if (!meta) return null;
            const Icon = PALETTE_ICONS[type] || Power;
            const count = counts[type] || 0;
            const active = activeType === type;
            return (
              <button
                key={type}
                type="button"
                onClick={() => onSelectType && onSelectType(type)}
                className={`flex items-center gap-1.5 rounded border px-2 py-1 transition-colors ${
                  active
                    ? 'border-purple-500 bg-purple-50 text-purple-700'
                    : 'border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300 hover:bg-neutral-50'
                }`}
                style={{ borderLeftWidth: 4, borderLeftColor: meta.color }}
                title={meta.label}
                aria-label={meta.label}
                aria-pressed={active}
              >
                <Icon size={14} strokeWidth={1.75} aria-hidden="true" />
                <span>{meta.label}</span>
                {count > 0 && (
                  <span
                    onClick={(e) => {
                      e.stopPropagation();
                      onHighlightType && onHighlightType(type);
                    }}
                    className="ml-1 rounded-full bg-neutral-200 px-1.5 text-[10px] font-mono font-semibold text-neutral-700"
                    title="Spustelėti — paryškinti visus šio tipo"
                  >× {count}</span>
                )}
              </button>
            );
          })}
        </React.Fragment>
      ))}
      <span className="ml-2 text-neutral-400">
        Dešinysis pelės klavišas = ištrinti. Vilkti = perkelti.
      </span>
    </div>
  );
}
