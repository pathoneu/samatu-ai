/**
 * OverlayLegend — the legend card for the drawing layers that are on (Pathon v3 W1-C): every line
 * style and colour the sheet shows, named once in words where the layer is — meaning never by colour
 * alone. Rows come from lib/overlayTokens LEGENDS, so the card and the layers cannot drift apart.
 */
import { LEGENDS, ov, paint } from '@/lib/overlayTokens';

function Swatch({ row }) {
  if (row.swatch === 'fill') {
    return (
      <svg width="16" height="12" aria-hidden="true">
        <rect x="1" y="1" width="14" height="10" rx="1" style={paint({ fill: ov(row.fill, 0.35), stroke: ov(row.stroke, 0.8) })} strokeWidth="1" />
      </svg>
    );
  }
  if (row.swatch === 'ring') {
    return (
      <svg width="16" height="16" aria-hidden="true">
        <circle cx="8" cy="8" r="6" style={paint({ fill: ov('label-bg'), stroke: ov(row.stroke) })} strokeWidth="1.5" />
      </svg>
    );
  }
  const bar = row.swatch === 'bar';
  return (
    <svg width="24" height="12" aria-hidden="true">
      {row.fill && <rect x="1" y="1" width="22" height="10" style={paint({ fill: ov(row.fill, 0.16) })} />}
      <line
        x1="2" y1="6" x2="22" y2="6"
        style={paint({ stroke: ov(row.stroke) })}
        strokeWidth={bar ? 4 : 2}
        strokeDasharray={row.dash || undefined}
      />
    </svg>
  );
}

// `vertical` (v3 W1-B): one row per line — a compact card the canvas chrome can move out of the way.
export default function OverlayLegend({ layers = [], className = '', vertical = false, ...rest }) {
  const rows = layers.flatMap((layer) => LEGENDS[layer] || []);
  if (!rows.length) return null;
  return (
    <div
      className={`rounded-panel border border-border bg-card/95 px-3 py-1.5 text-meta text-foreground shadow-md pointer-events-none flex ${vertical ? 'flex-col items-start gap-1' : 'flex-wrap items-center gap-x-3 gap-y-1'} ${className}`}
      {...rest}
    >
      {rows.map((row) => (
        <span key={row.key} className="inline-flex items-center gap-1.5">
          <Swatch row={row} />
          {row.label}
        </span>
      ))}
    </div>
  );
}
