/**
 * CountLegendPanel — standalone, props-driven legend for the "count" tool.
 * Lists each count type with a colored shape glyph, its label, and a running
 * tally. Clicking a row selects that type as the active count type.
 *
 * Purely presentational: no store, no PlanViewer import.
 */

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
}) {
  return (
    <div
      className="flex flex-col gap-1 p-2 rounded-lg border bg-card text-card-foreground"
      data-testid="count-legend-panel"
    >
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground px-1 pb-1">
        Skaičiavimas (vnt.)
      </h3>
      <div className="flex flex-col gap-0.5">
        {countTypes.map((type) => {
          const active = type.id === activeCountTypeId;
          const tally = tallies[type.id] || 0;
          return (
            <button
              key={type.id}
              type="button"
              onClick={() => onSelectType?.(type.id)}
              data-testid={`clegend-${type.id}`}
              aria-pressed={active}
              className={`flex items-center gap-2 px-2 py-1.5 rounded text-sm text-left transition-colors ${
                active
                  ? 'bg-primary/10 text-primary font-medium'
                  : 'hover:bg-accent hover:text-accent-foreground'
              }`}
            >
              <Glyph shape={type.shape} color={type.color} />
              <span className="flex-1 min-w-0 truncate">{type.label}</span>
              <span className="tabular-nums text-xs opacity-80 min-w-[1.5rem] text-right">
                {tally}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
