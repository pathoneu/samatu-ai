/**
 * PolygonEditor — active-edit Konva sub-tree for the Phase C-1 polygon tool.
 *
 * Renders ON TOP of committed polygons. Only the polygon currently
 * `selectedId` is editable here; everything else lives on a non-listening
 * layer in MarkupCanvas for perf.
 *
 * Imperative drag pattern: vertex circles use refs + .position() during
 * drag, commit to React state on dragend (5-10x faster than re-render
 * on every mousemove per Konva perf guide).
 */

import { useRef, useState } from 'react';
import { Group, Circle, Rect, Text as KonvaText } from 'react-konva';
import { nearestVertex, nearestEdge } from '@/lib/polygonGeometry';

const VERTEX_R = 6;
const VERTEX_HIT_R = 12;
const GHOST_R = 4;

export default function PolygonEditor({
  polygon,             // {id, points, ...} — the currently selected polygon
  allPolygons,         // {id, points}[] for snap targets
  pageNumber,           
  selectedVertexIndices = [],
  onVerticesUpdate,    // (newPoints, opLog) => void
  onVertexInsert,      // (index, vertex) => void
  onVertexDelete,      // (index) => void  (kept on API for Task 17)
  onSelectVertex,      // (index, multi) => void
  modKeysRef,          // {shift, alt}
  snapEnabled = true,
  snapTolerance = 12,
}) {
  if (!polygon) return null;

  const pts = polygon.points;

  return (
    <Group>
      {/* Edges first so vertex hit-areas are on top */}
      {pts.map((_, i) => {
        const a = pts[i];
        const b = pts[(i + 1) % pts.length];
        const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
        return (
          <Group key={`mid-${i}`}>
            {/* Midpoint ghost — Google Maps pattern */}
            <Circle
              x={mid.x} y={mid.y} radius={GHOST_R}
              fill="#00B8D9" opacity={0.35}
              onMouseDown={(e) => {
                e.cancelBubble = true;
                onVertexInsert(i + 1, mid);
              }}
              onMouseEnter={(e) => { e.target.opacity(0.85); e.target.getLayer().batchDraw(); }}
              onMouseLeave={(e) => { e.target.opacity(0.35); e.target.getLayer().batchDraw(); }}
            />
          </Group>
        );
      })}

      {/* Vertex handles */}
      {pts.map((p, i) => (
        <VertexHandle
          key={`v-${i}`}
          point={p}
          index={i}
          isSelected={selectedVertexIndices.includes(i)}
          selectedIndices={selectedVertexIndices}
          allPolygons={allPolygons}
          excludePolygonId={polygon.id}
          modKeysRef={modKeysRef}
          snapEnabled={snapEnabled}
          snapTolerance={snapTolerance}
          onSelect={onSelectVertex}
          onDragEnd={(newPoint) => {
            const newPts = pts.map((q, j) => j === i ? newPoint : q);
            onVerticesUpdate(newPts, {
              type: 'move-vertex',
              polygonId: polygon.id, index: i,
              from: p, to: newPoint,
            });
          }}
          onDragEndAll={(offset) => {
            const newPts = pts.map((q, j) =>
              selectedVertexIndices.includes(j)
                ? { x: q.x + offset.dx, y: q.y + offset.dy }
                : q,
            );
            onVerticesUpdate(newPts, {
              type: 'move-vertices-batch',
              polygonId: polygon.id,
              indices: [...selectedVertexIndices],
              offset,
            });
          }}
        />
      ))}
    </Group>
  );
}

function VertexHandle({
  point, index, isSelected, selectedIndices = [],
  allPolygons, excludePolygonId,
  modKeysRef, snapEnabled, snapTolerance,
  onSelect, onDragEnd, onDragEndAll,
}) {
  const ref = useRef(null);
  const startRef = useRef(null);
  const [snapTarget, setSnapTarget] = useState(null);
  const isMulti = isSelected && selectedIndices.length > 1;

  return (
    <>
      {/* Visible vertex */}
      <Circle
        x={point.x} y={point.y} radius={VERTEX_R}
        fill={isSelected ? '#00B8D9' : '#ffffff'}
        stroke="#00B8D9" strokeWidth={1.5}
        listening={false}
      />
      {/* Hit area (transparent, larger) */}
      <Circle
        ref={ref}
        x={point.x} y={point.y} radius={VERTEX_HIT_R}
        fill="rgba(0,0,0,0.001)"  // hit-graph requires non-zero alpha
        draggable
        onMouseDown={(e) => {
          e.cancelBubble = true;
          onSelect(index, modKeysRef?.current?.shift || false);
        }}
        onDragStart={() => {
          startRef.current = { x: point.x, y: point.y };
        }}
        onDragMove={(e) => {
          if (!snapEnabled || modKeysRef?.current?.alt) {
            setSnapTarget(null);
            return;
          }
          const pos = { x: e.target.x(), y: e.target.y() };
          const v = nearestVertex(pos, allPolygons, snapTolerance, { excludePolygonId });
          if (v) {
            e.target.position(v.point);
            setSnapTarget({ x: v.point.x, y: v.point.y, type: 'vertex', label: 'kampas' });
            return;
          }
          const ed = nearestEdge(pos, allPolygons, Math.round(snapTolerance * 0.66), { excludePolygonId });
          if (ed) {
            e.target.position(ed.point);
            setSnapTarget({ x: ed.point.x, y: ed.point.y, type: 'edge', label: 'kraštas' });
            return;
          }
          setSnapTarget(null);
        }}
        onDragEnd={(e) => {
          setSnapTarget(null);
          const newPos = { x: e.target.x(), y: e.target.y() };
          if (isMulti && onDragEndAll && startRef.current) {
            const dx = newPos.x - startRef.current.x;
            const dy = newPos.y - startRef.current.y;
            onDragEndAll({ dx, dy });
          } else {
            onDragEnd(newPos);
          }
          startRef.current = null;
        }}
      />
      {/* Snap indicator: cyan halo + Lithuanian label ("kampas" / "kraštas").
          Without this users disable snap and double-place vertices (UX research §3.4). */}
      {snapTarget && (
        <Group listening={false}>
          <Circle
            x={snapTarget.x} y={snapTarget.y} radius={10}
            stroke="#00B8D9" strokeWidth={2} opacity={0.6}
          />
          <Rect
            x={snapTarget.x + 12} y={snapTarget.y - 22}
            width={56} height={18}
            fill="rgba(15,23,42,0.85)" cornerRadius={3}
          />
          <KonvaText
            x={snapTarget.x + 16} y={snapTarget.y - 20}
            text={snapTarget.label} fontSize={11} fill="#e2e8f0"
          />
        </Group>
      )}
    </>
  );
}
