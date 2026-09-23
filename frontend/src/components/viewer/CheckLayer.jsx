/**
 * CheckLayer — what the check sheet READ about one room, drawn on the page.
 *
 * Patikra v2 (2026-09-19). One SVG per page, page-glued like RoomZoneLayer,
 * click-through. It draws only what `lib/checkOverlay` hands it for this page:
 *  • the room's traced OUTLINE (an open plan's shared outline dashed);
 *  • every WALL coloured by where its length came from, with the number(s)
 *    written along it — green: read on the plan; amber: taken from the equal
 *    wall opposite; grey: a short piece from the outline; red dashed: the plan
 *    writes no length for it;
 *  • the dimension STRINGS that were added, marked on the sheet they are on;
 *  • the IMAGINARY boundary a person drew through a space two rooms share — dashed
 *    in the room's blue: an edge of the outline, not a wall; and the points he has
 *    clicked so far while showing a room or dividing a space;
 *  • the boundary the program PROPOSES for a shared space, before it is accepted: both
 *    rooms' outlines with their numbers and the dashed line between them;
 *  • the OPENINGS the wall solid shows in the room's walls — a violet bar across
 *    each gap with its width beside it, ALWAYS (2026-09-21: the width used to appear
 *    only while the door-and-window fact was hovered — the founder never found it);
 *    the bar thickens while that fact is looked at;
 *  • the rectangle a fact was read from, solid while that fact is active;
 *  • the room's printed number, ringed, when the room has no outline of its own.
 *
 * While a boundary is being drawn (ONE point clicked, the second awaited) the line from
 * that point to the pointer is shown live — he sees the boundary before he sets it
 * (2026-09-21, founder: „nėra instrukcijų, tik tu ir aš jas žinom").
 *
 * Colours are on-drawing SEMANTIC colours (they must read on any sheet), not
 * theme tokens — same rule as the measure and zone layers. Coordinates are
 * display-space page fractions; PageOverlayHost's wrapper handles /Rotate.
 */

import { useEffect, useRef, useState } from 'react';

const STATE = {
  read: { stroke: '#15803d', dash: null },
  borrowed: { stroke: '#b45309', dash: null },
  outline: { stroke: '#64748b', dash: null },
  missing: { stroke: '#dc2626', dash: '7 5' },
};
const ROOM = '#1d4ed8';
const OPENING = '#7c3aed';
const CHIP_FONT = 11;

function chipWidth(label) {
  return Math.max(24, 10 + String(label).length * 6.3);
}

export default function CheckLayer({ data, renderedSize }) {
  const width = renderedSize?.width;
  const height = renderedSize?.height;
  const svgRef = useRef(null);
  const [pointer, setPointer] = useState(null);
  const drawing = (data?.pickPoints || []).length === 1;      // a boundary's first end is set
  useEffect(() => {
    if (!drawing || !width || !height) { setPointer(null); return undefined; }
    const onMove = (e) => {
      // screen → this SVG's own frame; the inverse CTM also undoes the page wrapper's /Rotate
      const ctm = svgRef.current?.getScreenCTM?.();
      if (!ctm) return;
      const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
      setPointer(p.x >= 0 && p.y >= 0 && p.x <= width && p.y <= height ? { x: p.x, y: p.y } : null);
    };
    window.addEventListener('pointermove', onMove);
    return () => window.removeEventListener('pointermove', onMove);
  }, [drawing, width, height]);
  if (!data || !width || !height) return null;
  const X = (p) => p[0] * width;
  const Y = (p) => p[1] * height;
  const poly = (pts) => pts.map((p) => `${X(p).toFixed(1)},${Y(p).toFixed(1)}`).join(' ');

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'visible' }}
      data-check-layer
    >
      {data.openSpace?.points?.length >= 3 && (
        <polygon
          points={poly(data.openSpace.points)}
          fill={ROOM}
          fillOpacity={0.05}
          stroke={ROOM}
          strokeWidth={2}
          strokeDasharray="10 6"
          strokeLinejoin="round"
        />
      )}
      {data.outline?.length >= 3 && (
        <polygon
          points={poly(data.outline)}
          fill={ROOM}
          fillOpacity={0.07}
          stroke={ROOM}
          strokeOpacity={data.walls?.length ? 0.25 : 1}
          strokeWidth={data.walls?.length ? 1 : 2.5}
          strokeLinejoin="round"
        />
      )}

      {(data.strings || []).map((s, i) => (
        <g key={`s${i}`}>
          <line
            x1={X(s.a)} y1={Y(s.a)} x2={X(s.b)} y2={Y(s.b)}
            stroke={STATE.read.stroke} strokeOpacity={0.55} strokeWidth={6} strokeLinecap="round"
          />
        </g>
      ))}

      {(data.walls || []).map((w, i) => {
        const st = STATE[w.state] || STATE.missing;
        return (
          <line
            key={`w${i}`}
            x1={X(w.a)} y1={Y(w.a)} x2={X(w.b)} y2={Y(w.b)}
            stroke={st.stroke} strokeWidth={3.5} strokeLinecap="round"
            strokeDasharray={st.dash || undefined}
          />
        );
      })}
      {/* the boundary the program PROPOSES for a shared space — shown before it is accepted: both rooms' outlines,
          their numbers, and the dashed line between them */}
      {data.proposal && (
        <g data-check-proposal>
          {data.proposal.outlines.map((o) => {
            const cx = o.points.reduce((sum, pt) => sum + X(pt), 0) / o.points.length;
            const cy = o.points.reduce((sum, pt) => sum + Y(pt), 0) / o.points.length;
            return (
              <g key={`pr${o.nr}`}>
                <polygon
                  points={poly(o.points)} fill={ROOM} fillOpacity={0.1} stroke={ROOM} strokeWidth={data.proposal.line ? 2 : 3}
                  strokeLinejoin="round" strokeDasharray={data.proposal.line ? undefined : '9 6'}
                />
                <g transform={`translate(${cx.toFixed(1)}, ${cy.toFixed(1)})`}>
                  <rect x={-16} y={-11} width={32} height={22} rx={2} fill={ROOM} />
                  <text x={0} y={5} textAnchor="middle" fontSize={13} fontFamily="'IBM Plex Mono', ui-monospace, monospace" fontWeight={600} fill="#ffffff">{o.nr}</text>
                </g>
              </g>
            );
          })}
          {data.proposal.line && (
            <>
              <line
                x1={X(data.proposal.line[0])} y1={Y(data.proposal.line[0])} x2={X(data.proposal.line[1])} y2={Y(data.proposal.line[1])}
                stroke="#ffffff" strokeWidth={7} strokeLinecap="round"
              />
              <line
                x1={X(data.proposal.line[0])} y1={Y(data.proposal.line[0])} x2={X(data.proposal.line[1])} y2={Y(data.proposal.line[1])}
                stroke={ROOM} strokeWidth={3.5} strokeDasharray="10 7" strokeLinecap="round"
              />
            </>
          )}
        </g>
      )}

      {(data.imaginary || []).map((seg, i) => (
        <line
          key={`im${i}`} data-check-imaginary
          x1={X(seg.a)} y1={Y(seg.a)} x2={X(seg.b)} y2={Y(seg.b)}
          stroke={ROOM} strokeWidth={2.5} strokeDasharray="9 6" strokeLinecap="round"
        />
      ))}

      {(data.openings || []).map((g, i) => (
        <g key={`o${i}`} data-check-opening>
          <line x1={X(g.a)} y1={Y(g.a)} x2={X(g.b)} y2={Y(g.b)} stroke="#ffffff" strokeOpacity={0.9} strokeWidth={9} strokeLinecap="round" />
          <line
            x1={X(g.a)} y1={Y(g.a)} x2={X(g.b)} y2={Y(g.b)}
            stroke={OPENING} strokeWidth={g.active ? 6 : 4.5} strokeLinecap="round" strokeOpacity={g.active ? 1 : 0.8}
          />
        </g>
      ))}
      {/* wall lengths go ON TOP of the opening bars: a bar runs along the same wall and used to cut the number in half */}
      {(data.walls || []).map((w, i) => {
        const st = STATE[w.state] || STATE.missing;
        const cx = (X(w.a) + X(w.b)) / 2;
        const cy = (Y(w.a) + Y(w.b)) / 2;
        const len = Math.hypot(X(w.b) - X(w.a), Y(w.b) - Y(w.a));
        const cw = chipWidth(w.label);
        if (len < 18) return null;                       // a wall too short on screen to carry a chip
        return (
          <g key={`c${i}`} transform={`translate(${cx.toFixed(1)}, ${cy.toFixed(1)})`}>
            <rect x={-cw / 2} y={-9} width={cw} height={18} rx={2} fill="#ffffff" fillOpacity={0.94} stroke={st.stroke} strokeWidth={1.2} />
            <text
              x={0} y={4} textAnchor="middle" fontSize={CHIP_FONT}
              fontFamily="'IBM Plex Mono', ui-monospace, monospace" fontWeight={600} fill={st.stroke}
            >
              {w.label}
            </text>
          </g>
        );
      })}

      {(data.openings || []).filter((g) => g.label).map((g, i) => {
        // the chip stands OUTSIDE the room, clear of the wall's own length chip
        const mx = (X(g.a) + X(g.b)) / 2;
        const my = (Y(g.a) + Y(g.b)) / 2;
        const ring = data.outline?.length >= 3 ? data.outline : null;
        const cx = ring ? ring.reduce((sum, p) => sum + X(p), 0) / ring.length : mx;
        const cy = ring ? ring.reduce((sum, p) => sum + Y(p), 0) / ring.length : my;
        const len = Math.hypot(X(g.b) - X(g.a), Y(g.b) - Y(g.a)) || 1;
        let nx = -(Y(g.b) - Y(g.a)) / len;
        let ny = (X(g.b) - X(g.a)) / len;
        if (nx * (mx - cx) + ny * (my - cy) < 0) { nx = -nx; ny = -ny; }
        const cw = chipWidth(g.label);
        // far enough out that it clears the wall's own chip whichever way the wall runs: chips are
        // wide and low, so beside a VERTICAL wall the two would overlap at the old fixed 22 px
        const off = Math.abs(nx) * (20 + cw / 2) + Math.abs(ny) * 18 + 4;
        return (
          <g key={`oc${i}`} transform={`translate(${(mx + nx * off).toFixed(1)}, ${(my + ny * off).toFixed(1)})`}>
            <rect x={-cw / 2} y={-9} width={cw} height={18} rx={2} fill={OPENING} stroke="#ffffff" strokeWidth={1.2} />
            <text
              x={0} y={4} textAnchor="middle" fontSize={CHIP_FONT}
              fontFamily="'IBM Plex Mono', ui-monospace, monospace" fontWeight={600} fill="#ffffff"
            >
              {g.label}
            </text>
          </g>
        );
      })}

      {(data.marks || []).map((m) => {
        const [x0, y0, x1, y1] = m.rect;
        return (
          <rect
            key={`m-${m.key}`}
            x={x0 * width} y={y0 * height} width={(x1 - x0) * width} height={(y1 - y0) * height}
            fill={m.active ? '#f59e0b' : 'none'} fillOpacity={m.active ? 0.12 : 0}
            stroke="#d97706" strokeWidth={m.active ? 2.5 : 1.5} strokeDasharray={m.active ? undefined : '6 4'}
          />
        );
      })}

      {drawing && pointer && (() => {
        // the boundary as it will be cut: through both points, carried on past them towards the walls
        const ax = data.pickPoints[0].x * width;
        const ay = data.pickPoints[0].y * height;
        const len = Math.hypot(pointer.x - ax, pointer.y - ay);
        if (len < 4) return null;
        const ux = (pointer.x - ax) / len;
        const uy = (pointer.y - ay) / len;
        return (
          <g data-check-pick-line>
            <line x1={ax - ux * 70} y1={ay - uy * 70} x2={pointer.x + ux * 70} y2={pointer.y + uy * 70}
              stroke={ROOM} strokeOpacity={0.35} strokeWidth={2} strokeDasharray="4 6" strokeLinecap="round" />
            <line x1={ax} y1={ay} x2={pointer.x} y2={pointer.y}
              stroke={ROOM} strokeWidth={2.5} strokeDasharray="9 6" strokeLinecap="round" />
          </g>
        );
      })()}

      {(data.pickPoints || []).map((pt, i) => (
        <g key={`pk${i}`} transform={`translate(${(pt.x * width).toFixed(1)}, ${(pt.y * height).toFixed(1)})`} data-check-pick>
          <circle r={7} fill="#ffffff" fillOpacity={0.9} stroke={ROOM} strokeWidth={2.5} />
          <line x1={-11} y1={0} x2={11} y2={0} stroke={ROOM} strokeWidth={1.5} />
          <line x1={0} y1={-11} x2={0} y2={11} stroke={ROOM} strokeWidth={1.5} />
        </g>
      ))}

      {data.marker && (
        <g transform={`translate(${(data.marker.x * width).toFixed(1)}, ${(data.marker.y * height).toFixed(1)})`}>
          <circle r={16} fill="none" stroke="#dc2626" strokeWidth={2.5} />
          <circle r={22} fill="none" stroke="#dc2626" strokeOpacity={0.35} strokeWidth={2} />
        </g>
      )}
    </svg>
  );
}
