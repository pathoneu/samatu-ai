/**
 * CheckLayer — what the check sheet READ about one room, drawn on the page.
 *
 * Patikra v2 (2026-09-19). One SVG per page, page-glued like RoomZoneLayer,
 * click-through. It draws only what `lib/checkOverlay` hands it for this page:
 *  • the room's traced OUTLINE (an open plan's shared outline fainter);
 *  • every WALL styled by where its length came from, with the number(s)
 *    written along it — solid evergreen: read on the plan; dashed amber: taken
 *    from the equal wall opposite; solid slate: a short piece from the outline;
 *    solid red: the plan writes no length for it;
 *  • the dimension STRINGS that were added, marked on the sheet they are on;
 *  • the IMAGINARY boundary a person drew through a space two rooms share — solid
 *    in the room's ink (he drew it): an edge of the outline, not a wall; and the points he has
 *    clicked so far while showing a room or dividing a space;
 *  • the boundary the program PROPOSES for a shared space, before it is accepted: both
 *    rooms' outlines (dashed proposal blue) with their numbers and the dashed line between them;
 *  • the OPENINGS the wall solid shows in the room's walls — a violet bar across
 *    each gap with its width beside it, ALWAYS (2026-09-21: the width used to appear
 *    only while the door-and-window fact was hovered — the founder never found it);
 *    the bar thickens while that fact is looked at;
 *  • the rectangle a fact was read from (evergreen), heavier while that fact is active;
 *  • the room's printed number, ringed, when the room has no outline of its own.
 *
 * While a boundary is being drawn (ONE point clicked, the second awaited) the line from
 * that point to the pointer is shown live — he sees the boundary before he sets it
 * (2026-09-21, founder: „nėra instrukcijų, tik tu ir aš jas žinom").
 *
 * v3 overlay vocabulary (2026-10-18; lib/overlayTokens — the Patikra code became the whole viewer's
 * code): a wall READ on the plan is solid evergreen; one borrowed from the equal wall opposite is an
 * ESTIMATE — amber, the one dash; a piece measured off the outline is solid slate; a wall the plan gives
 * NO length is red (the one thing to fix); the room's own outline and its number are the selection's
 * neutral ink; a boundary the program PROPOSES is the dashed proposal blue; openings violet; chips are
 * label pills in the app's sans (12 px, tabular numbers). Coordinates are display-space page
 * fractions; PageOverlayHost's wrapper handles /Rotate.
 */

import { useEffect, useRef, useState } from 'react';
import { DASH, LABEL_FONT_PX, LABEL_STYLE, SELECTED_STROKE_PX, labelWidth, ov, paint } from '@/lib/overlayTokens';

// Where a wall's length came from (lib/checkOverlay.wallState) → its line. Exported for the legend.
export const WALL_STATE_STYLE = {
  read: { stroke: ov('read'), dash: null },
  borrowed: { stroke: ov('estimated'), dash: DASH },
  outline: { stroke: ov('wall'), dash: null },
  missing: { stroke: ov('error'), dash: null },
};
const STATE = WALL_STATE_STYLE;
const ROOM = ov('selected');
const PROPOSED = ov('proposed');
const OPENING = ov('opening');
const WHITE = ov('label-bg');
const CHIP_FONT = LABEL_FONT_PX;

function chipWidth(label) {
  return Math.max(26, labelWidth(label));
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
          style={paint({ fill: ROOM, stroke: ROOM })}
          fillOpacity={0.05}
          strokeOpacity={0.55}
          strokeWidth={2}
          strokeLinejoin="round"
        />
      )}
      {data.outline?.length >= 3 && (
        <polygon
          points={poly(data.outline)}
          style={paint({ fill: ROOM, stroke: ROOM })}
          fillOpacity={0.06}
          strokeOpacity={data.walls?.length ? 0.3 : 1}
          strokeWidth={data.walls?.length ? 1 : SELECTED_STROKE_PX}
          strokeLinejoin="round"
        />
      )}

      {(data.strings || []).map((s, i) => (
        <g key={`s${i}`}>
          <line
            x1={X(s.a)} y1={Y(s.a)} x2={X(s.b)} y2={Y(s.b)}
            style={paint({ stroke: STATE.read.stroke })} strokeOpacity={0.45} strokeWidth={6} strokeLinecap="round"
          />
        </g>
      ))}

      {(data.walls || []).map((w, i) => {
        const st = STATE[w.state] || STATE.missing;
        return (
          <line
            key={`w${i}`}
            x1={X(w.a)} y1={Y(w.a)} x2={X(w.b)} y2={Y(w.b)}
            style={paint({ stroke: st.stroke })} strokeWidth={3.5} strokeLinecap={st.dash ? 'butt' : 'round'}
            strokeDasharray={st.dash || undefined}
            data-wall-state={w.state}
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
                  points={poly(o.points)} style={paint({ fill: PROPOSED, stroke: PROPOSED })} fillOpacity={0.1} strokeWidth={data.proposal.line ? 2 : SELECTED_STROKE_PX}
                  strokeLinejoin="round" strokeDasharray={DASH}
                />
                <g transform={`translate(${cx.toFixed(1)}, ${cy.toFixed(1)})`}>
                  <rect x={-17} y={-11} width={34} height={22} rx={2} style={paint({ fill: WHITE, stroke: PROPOSED })} strokeWidth={1.5} />
                  <text x={0} y={4} textAnchor="middle" fontSize={CHIP_FONT} fontWeight={600} style={{ ...LABEL_STYLE, ...paint({ fill: ov('label-fg') }) }}>{o.nr}</text>
                </g>
              </g>
            );
          })}
          {data.proposal.line && (
            <>
              <line
                x1={X(data.proposal.line[0])} y1={Y(data.proposal.line[0])} x2={X(data.proposal.line[1])} y2={Y(data.proposal.line[1])}
                style={paint({ stroke: WHITE })} strokeWidth={7} strokeLinecap="round"
              />
              <line
                x1={X(data.proposal.line[0])} y1={Y(data.proposal.line[0])} x2={X(data.proposal.line[1])} y2={Y(data.proposal.line[1])}
                style={paint({ stroke: PROPOSED })} strokeWidth={3.5} strokeDasharray={DASH}
              />
            </>
          )}
        </g>
      )}

      {(data.imaginary || []).map((seg, i) => (
        <line
          key={`im${i}`} data-check-imaginary
          x1={X(seg.a)} y1={Y(seg.a)} x2={X(seg.b)} y2={Y(seg.b)}
          style={paint({ stroke: ROOM })} strokeWidth={2.5} strokeLinecap="round"
        />
      ))}

      {(data.openings || []).map((g, i) => (
        <g key={`o${i}`} data-check-opening>
          <line x1={X(g.a)} y1={Y(g.a)} x2={X(g.b)} y2={Y(g.b)} style={paint({ stroke: WHITE })} strokeOpacity={0.9} strokeWidth={9} strokeLinecap="round" />
          <line
            x1={X(g.a)} y1={Y(g.a)} x2={X(g.b)} y2={Y(g.b)}
            style={paint({ stroke: OPENING })} strokeWidth={g.active ? 6 : 4.5} strokeLinecap="round" strokeOpacity={g.active ? 1 : 0.85}
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
            <rect x={-cw / 2} y={-10} width={cw} height={20} rx={2} style={paint({ fill: WHITE, stroke: st.stroke })} fillOpacity={0.96} strokeWidth={1.5}
              strokeDasharray={st.dash || undefined} />
            <text
              x={0} y={4} textAnchor="middle" fontSize={CHIP_FONT} fontWeight={600}
              style={{ ...LABEL_STYLE, ...paint({ fill: ov('label-fg') }) }}
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
            <rect x={-cw / 2} y={-10} width={cw} height={20} rx={2} style={paint({ fill: OPENING, stroke: WHITE })} strokeWidth={1.2} />
            <text
              x={0} y={4} textAnchor="middle" fontSize={CHIP_FONT} fontWeight={600}
              style={{ ...LABEL_STYLE, ...paint({ fill: WHITE }) }}
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
            style={paint({ fill: m.active ? ov('read') : null, stroke: ov('read') })}
            fill={m.active ? undefined : 'none'} fillOpacity={m.active ? 0.12 : 0}
            strokeWidth={m.active ? 2.5 : 1.5} strokeOpacity={m.active ? 1 : 0.6}
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
              style={paint({ stroke: PROPOSED })} strokeOpacity={0.4} strokeWidth={2} strokeDasharray={DASH} />
            <line x1={ax} y1={ay} x2={pointer.x} y2={pointer.y}
              style={paint({ stroke: PROPOSED })} strokeWidth={2.5} strokeDasharray={DASH} />
          </g>
        );
      })()}

      {(data.pickPoints || []).map((pt, i) => (
        <g key={`pk${i}`} transform={`translate(${(pt.x * width).toFixed(1)}, ${(pt.y * height).toFixed(1)})`} data-check-pick>
          <circle r={7} style={paint({ fill: WHITE, stroke: PROPOSED })} fillOpacity={0.9} strokeWidth={2.5} />
          <line x1={-11} y1={0} x2={11} y2={0} style={paint({ stroke: PROPOSED })} strokeWidth={1.5} />
          <line x1={0} y1={-11} x2={0} y2={11} style={paint({ stroke: PROPOSED })} strokeWidth={1.5} />
        </g>
      ))}

      {data.marker && (
        <g transform={`translate(${(data.marker.x * width).toFixed(1)}, ${(data.marker.y * height).toFixed(1)})`}>
          <circle r={16} fill="none" style={paint({ stroke: WHITE })} strokeWidth={SELECTED_STROKE_PX + 3} opacity={0.9} />
          <circle r={16} fill="none" style={paint({ stroke: ROOM })} strokeWidth={SELECTED_STROKE_PX} />
          <circle r={22} fill="none" style={paint({ stroke: ROOM })} strokeOpacity={0.35} strokeWidth={2} />
        </g>
      )}
    </svg>
  );
}
