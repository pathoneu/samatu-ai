/**
 * CountLegendPanel — standalone, props-driven legend for the "count" tool.
 * Lists each USER-DEFINED count type (founder 2026-07-14: no fixed list) with
 * a colored glyph, label, running tally, and a per-type clear/remove action.
 * "+ Pridėti tipą" creates a new type inline. Clicking a row selects it as
 * the active count type.
 *
 * Purely presentational: no store, no PlanViewer import.
 */
import { useState } from 'react';

function Glyph({ shape, color }) {
  const size = 14;
  const half = size / 2;
  switch (shape) {
    case 'square':
      return (
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
          <rect x={1} y={1} width={size - 2} height={size - 2} fill={color} />
        </svg>
      );
    case 'diamond':
      return (
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
          <path d={`M ${half} 1 L ${size - 1} ${half} L ${half} ${size - 1} L 1 ${half} Z`} fill={color} />
        </svg>
      );
    case 'check':
      return (
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
          <circle cx={half} cy={half} r={half - 1} fill="none" stroke={color} strokeWidth={1.5} />
          <path
            d={`M ${half - 3} ${half} L ${half - 1} ${half + 3} L ${half + 4} ${half - 3}`}
            fill="none"
            stroke={color}
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case 'circle':
    default:
      return (
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
          <circle cx={half} cy={half} r={half - 1} fill={color} />
        </svg>
      );
  }
}

export default function CountLegendPanel({
  countTypes = [],
  activeCountTypeId = null,
  onSelectType,
  tallies = {},
  // {typeId: n} marks added by „Rasti panašius" (lib/symbolSearch.aiTallies) — found by
  // shape, not checked; drawn hollow on the sheet.
  aiTallies = {},
  // The panel floats OVER the canvas and swallows placement clicks in the
  // region it covers (audit P2) — collapsible so the user can tuck it away.
  collapsed = false,
  onToggleCollapse = null,
  // Per-type "clear all marks" (audit P3). Only shown when the type has marks.
  onClearType = null,
  // Custom types: create / remove (remove only offered when the type is empty).
  onAddType = null,
  onRemoveType = null,
}) {
  const [adding, setAdding] = useState(false);
  const [newLabel, setNewLabel] = useState('');
  const submitNew = () => {
    const v = newLabel.trim();
    if (v) onAddType?.(v);
    setNewLabel('');
    setAdding(false);
  };
  return (
    <div
      className="flex flex-col gap-1 p-2 rounded-lg border bg-card text-card-foreground"
      data-testid="count-legend-panel"
    >
      <div className="flex items-center px-1 pb-1">
        <h3
          className="text-xs font-semibold uppercase tracking-wide text-muted-foreground flex-1"
          title="Vienetų skaičiavimas: sukurkite tipą (pvz., rozetės), pažymėkite jį ir spustelėkite kiekvieną elementą brėžinyje"
        >
          Skaičiavimas (vnt.)
        </h3>
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-expanded={!collapsed}
            title={collapsed ? 'Išskleisti tipų sąrašą' : 'Suskleisti sąrašą — žymėti brėžinyje galėsite toliau'}
            className="p-0.5 rounded text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          >
            <svg width={12} height={12} viewBox="0 0 12 12" aria-hidden="true">
              <path
                d={collapsed ? 'M 3 7.5 L 6 4.5 L 9 7.5' : 'M 3 4.5 L 6 7.5 L 9 4.5'}
                fill="none" stroke="currentColor" strokeWidth={1.5}
                strokeLinecap="round" strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
      </div>
      {!collapsed && (
      <div className="flex flex-col gap-0.5">
        {countTypes.map((type) => {
          const active = type.id === activeCountTypeId;
          const tally = tallies[type.id] || 0;
          const ai = aiTallies[type.id] || 0;
          return (
            <button
              key={type.id}
              type="button"
              onClick={() => onSelectType?.(type.id)}
              data-testid={`clegend-${type.id}`}
              aria-pressed={active}
              /* Selecting a type is what makes clicks on the drawing land —
                 nothing said so, and the colour/shape are auto-assigned, which
                 users read as a picker. (2026-07-28.) */
              title={active
                ? `„${type.label}" pažymėtas — spustelėkite elementus brėžinyje. Pažymėta: ${tally} vnt.`
                : `Skaičiuoti „${type.label}" — spalvą ir formą programa priskiria automatiškai`}
              className={`flex items-center gap-2 px-2 py-1.5 rounded text-sm text-left transition-colors ${
                active
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'hover:bg-accent hover:text-accent-foreground'
              }`}
            >
              <Glyph shape={type.shape} color={type.color} />
              {/* The name keeps the row; „N rasta automatiškai" sits under it (2026-10-18: beside it, the
                  longer Lithuanian words cut the name down to one letter). */}
              <span className="flex-1 min-w-0 flex flex-col items-start">
                <span className="max-w-full truncate">{type.label}</span>
                {ai > 0 && (
                  <span
                    className="inline-flex items-center gap-0.5 px-1 rounded-sm text-[10px] leading-4 bg-[hsl(var(--conf-med)/0.12)] text-[hsl(var(--conf-med))]"
                    title={`${ai} iš ${tally} rasta automatiškai („Rasti panašius") — tuščiavidurės žymės brėžinyje, patikrinkite`}
                    data-testid={`clegend-ai-${type.id}`}
                  >
                    {ai} rasta automatiškai
                  </span>
                )}
              </span>
              <span
                className="tabular-nums text-xs opacity-80 min-w-[1.5rem] text-right"
                title={`Pažymėta ${tally} vnt.`}
              >
                {tally}
              </span>
              {onRemoveType && tally === 0 && (
                <span
                  role="button"
                  tabIndex={0}
                  data-testid={`clegend-remove-${type.id}`}
                  /* Same × glyph as the clear-all below. Disambiguate in words:
                     this one removes an EMPTY type, that one wipes N marks. */
                  title={`Pašalinti tipą „${type.label}" iš sąrašo (žymėjimų nėra)`}
                  aria-label={`Pašalinti tipą ${type.label}`}
                  onClick={(e) => { e.stopPropagation(); onRemoveType(type.id); }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); onRemoveType(type.id); }
                  }}
                  className="p-0.5 rounded text-muted-foreground hover:text-destructive"
                >
                  <svg width={11} height={11} viewBox="0 0 11 11" aria-hidden="true">
                    <path d="M 2.5 2.5 L 8.5 8.5 M 8.5 2.5 L 2.5 8.5" stroke="currentColor" strokeWidth={1.4} strokeLinecap="round" />
                  </svg>
                </span>
              )}
              {onClearType && tally > 0 && (
                <span
                  role="button"
                  tabIndex={0}
                  data-testid={`clegend-clear-${type.id}`}
                  title={`Ištrinti visus „${type.label}" žymėjimus brėžinyje (${tally} vnt.) — atstatyti negalėsite`}
                  aria-label={`Ištrinti visus ${type.label} žymėjimus, ${tally} vnt.`}
                  onClick={(e) => { e.stopPropagation(); onClearType(type.id); }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); onClearType(type.id); }
                  }}
                  className="p-0.5 rounded text-muted-foreground hover:text-destructive"
                >
                  <svg width={11} height={11} viewBox="0 0 11 11" aria-hidden="true">
                    <path d="M 2.5 2.5 L 8.5 8.5 M 8.5 2.5 L 2.5 8.5" stroke="currentColor" strokeWidth={1.4} strokeLinecap="round" />
                  </svg>
                </span>
              )}
            </button>
          );
        })}
        {Object.values(aiTallies).some((n) => n > 0) && (
          <p className="flex items-center gap-1.5 px-2 pt-1 text-[11px] text-muted-foreground leading-snug" data-testid="clegend-ai-note">
            <svg width={12} height={12} viewBox="0 0 12 12" aria-hidden="true" className="shrink-0">
              <circle cx={6} cy={6} r={4.5} fill="none" stroke="currentColor" strokeWidth={1.6} />
            </svg>
            Tuščiavidurė žymė — rasta automatiškai, patikrinkite; pilna — pažymėta ranka.
          </p>
        )}
        {countTypes.length === 0 && !adding && (
          <p className="px-2 py-1 text-xs text-muted-foreground">
            Sukurkite tipą, kurį skaičiuosite (pvz., „Rozetės").
          </p>
        )}
        {onAddType && (adding ? (
          <input
            autoFocus
            type="text"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); submitNew(); }
              else if (e.key === 'Escape') { e.preventDefault(); setNewLabel(''); setAdding(false); }
            }}
            onBlur={submitNew}
            placeholder="Tipo pavadinimas…"
            aria-label="Naujo tipo pavadinimas"
            title="Įrašykite, ką skaičiuosite (pvz., Rozetės), ir paspauskite Enter · Esc — atsisakyti"
            data-testid="clegend-new-type-input"
            className="mx-1 mb-1 px-2 py-1 rounded border border-border bg-background text-sm focus:outline-none focus:border-primary"
          />
        ) : (
          <button
            type="button"
            data-testid="clegend-add-type"
            onClick={() => setAdding(true)}
            title="Sukurti naują skaičiuojamų elementų tipą (pvz., Rozetės, Šviestuvai)"
            className="flex items-center gap-2 px-2 py-1.5 rounded text-sm text-left text-primary hover:bg-accent"
          >
            <span className="text-base leading-none">＋</span>
            <span>Pridėti tipą</span>
          </button>
        ))}
      </div>
      )}
    </div>
  );
}
