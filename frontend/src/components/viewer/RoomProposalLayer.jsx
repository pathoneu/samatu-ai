/**
 * RoomProposalLayer — what the room tool R proposes on this sheet (Pathon v3 W1-D, D2): the outline it read
 * off the walls, DASHED in the proposal blue (W1-C vocabulary: dashed = proposed, not saved yet), its
 * consequence in one label pill beside it, and while the server reads, one pill at the click. Nothing here is
 * saved — the viewer saves on his next click or Enter, Esc drops it.
 *
 * Display-space page fractions, like every room layer; PageOverlayHost's wrapper handles /Rotate.
 * Pointer-transparent: the click goes to the page (TakeoffViewer.handlePagePoint), which decides.
 */
import { DASH, FILL_ALPHA, SELECTED_STROKE_PX, LINE_KINDS, labelWidth, ov, paint } from '@/lib/overlayTokens';
import OverlayLabel from './OverlayLabel';

function centreOf(ring, W, H) {
  const xs = ring.map(([x]) => x * W);
  const ys = ring.map(([, y]) => y * H);
  return { x: (Math.min(...xs) + Math.max(...xs)) / 2, y: (Math.min(...ys) + Math.max(...ys)) / 2, top: Math.min(...ys) };
}

export default function RoomProposalLayer({ page, state, renderedSize }) {
  const W = renderedSize?.width;
  const H = renderedSize?.height;
  if (!W || !H || !state) return null;
  const proposal = state.proposal && Number(state.proposal.page) === Number(page) ? state.proposal : null;
  const reading = state.phase === 'reading' && Number(state.reading?.page) === Number(page) ? state.reading : null;
  if (!proposal && !reading) return null;
  const stroke = ov('proposed');
  return (
    <svg width={W} height={H} className="absolute left-0 top-0" style={{ pointerEvents: 'none', overflow: 'visible' }} data-room-proposal={proposal ? proposal.nr : 'reading'}>
      {proposal && (() => {
        const pts = proposal.ring.map(([x, y]) => `${(x * W).toFixed(1)},${(y * H).toFixed(1)}`).join(' ');
        const c = centreOf(proposal.ring, W, H);
        const saving = state.phase === 'saving';
        return (
          <g>
            <title>{LINE_KINDS.proposed.sentence}</title>
            <polygon
              points={pts}
              style={paint({ fill: stroke, stroke })}
              fillOpacity={FILL_ALPHA}
              strokeWidth={SELECTED_STROKE_PX}
              strokeDasharray={DASH}
              strokeLinejoin="round"
            />
            {(() => {
              // The pill on the drawing says how to save or drop it (one place per instruction, W1-C);
              // this label says what saving changes — kept inside the sheet.
              const title = proposal.lines?.title || `Patalpa ${proposal.nr}`;
              const sub = saving ? 'Saugoma…' : (proposal.lines?.sub || null);
              const half = Math.max(labelWidth(title), labelWidth(sub || '')) / 2;
              const x = Math.min(Math.max(c.x, half + 4), W - half - 4);
              return (
                <OverlayLabel x={x} y={Math.max(24, c.top - 26)} text={title} sub={sub} border={stroke} data-room-proposal-label />
              );
            })()}
          </g>
        );
      })()}
      {reading && (
        <OverlayLabel
          x={reading.x_pct * W}
          y={Math.max(16, reading.y_pct * H - 22)}
          text="Brėžiu kontūrą pagal sienas…"
          border={stroke}
          strong={false}
        />
      )}
    </svg>
  );
}

/** „Kuri tai patalpa?" — the click named no room; he says which (rooms without an outline first). */
export function RoomPickPanel({ picking, onPick, onCancel, left = 12 }) {
  if (!picking) return null;
  const list = picking.candidates || [];
  return (
    <div
      className="absolute top-2 z-panel w-72 max-h-[60%] overflow-y-auto rounded-panel border border-border bg-card text-card-foreground shadow-lg"
      style={{ left }}
      data-testid="room-tool-pick"
    >
      <div className="px-3 py-2 border-b border-border">
        <p className="text-ui font-semibold">Kuri tai patalpa?</p>
        <p className="text-meta text-muted-foreground">Čia programa patalpos numerio neatpažino. Pasirinkite — kontūrą nubrėšiu pagal sienas.</p>
      </div>
      <ul className="py-1">
        {list.map((c) => (
          <li key={c.nr}>
            <button
              type="button"
              className="w-full text-left px-3 py-1.5 text-ui hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => onPick(c.nr)}
            >
              <span className="mono tabular font-semibold mr-2">{c.nr}</span>{c.name}
            </button>
          </li>
        ))}
      </ul>
      <div className="px-3 py-2 border-t border-border flex justify-end">
        <button type="button" className="px-2 py-1 rounded text-ui text-foreground hover:bg-muted" onClick={onCancel}>Atšaukti</button>
      </div>
    </div>
  );
}
