/**
 * LegendTool — „Pažymėti legendą" (key G; Pathon v3 W2-B, design 2026-10-18 §4 B and §5 „Legend (G)").
 *
 *   useLegendTool — the session (lives in TakeoffViewer: the page hosts unmount when they scroll away):
 *     G → the visible sheet's legend is PROPOSED (dashed box, „Tai legenda? Taip / Nubrėžti kitaip" in the
 *     pill) — or, with none found, he drags a box over it; the rows are read and counted; he reviews them
 *     (LegendReviewPanel) and the marks on the drawing; ONE „Sukurti kiekius (N)" creates them — with Undo.
 *   LegendLayer — one page's part: the proposals, the box being dragged, the accepted legend and the found
 *     marks (hollow, dashed: proposals until created; a click on one removes it).
 *
 * Every reading starts from a proposal (founder decision 3, 2026-10-18); nothing exists before the click;
 * the routes it calls save nothing and cost nothing (lib/legendApi).
 */
import { useCallback, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  boxFromPctDrag, buildCreate, decisionsFor, initialReview, instanceId, journalRows, legendRowsToSave,
  blankRows, matchSavedLegend, pointInBox, proposalsFrom, rowsOf, rowsToCreate,
} from '@/lib/legendReview';
import {
  countLegendRows, fetchLegendRows, loadArchitectLegend, loadProjectLegend, promoteArchitectLegend, readArchitects,
  rememberArchitect, saveProjectLegend, sendLegendLearning,
} from '@/lib/legendApi';
import { klassFor } from '@/lib/symbolSearch';
import { flashCursorHint } from '@/lib/cursorHints';
import { DASH, LABEL_FONT_PX, LABEL_STYLE, STROKE_PX, labelWidth, ov, paint } from '@/lib/overlayTokens';

const EMPTY = {
  phase: null, page: null, proposals: [], legends: [], rows: [], counts: {}, review: {}, removed: new Set(),
  notice: null, reuse: null, architect: '', hoveredId: null, hoveredRowId: null,
};

/** The earlier legend this one matches, if any: this project's own saved one first, then his architects'. */
async function findReuse(projectId, rows) {
  try {
    const own = await loadProjectLegend(projectId);
    const fit = matchSavedLegend(rows, own);
    if (fit) return { ...fit, architect: own.architect || '', from: 'sis' };
  } catch { /* nothing saved yet */ }
  const architects = Object.entries(readArchitects()).slice(-5).reverse();
  for (const [name, projects] of architects) {
    try {
      const arch = await loadArchitectLegend(projectId, name);
      const fit = matchSavedLegend(rows, arch);
      if (fit) return { ...fit, architect: name, from: 'architektas' };
    } catch { /* go on */ }
    for (const other of [...(projects || [])].reverse().filter((p) => p !== projectId).slice(0, 2)) {
      try {
        const leg = await loadProjectLegend(other);
        const fit = matchSavedLegend(rows, leg);
        if (fit) return { ...fit, architect: name, from: 'projektas' };
      } catch { /* a deleted or foreign project */ }
    }
  }
  return null;
}

export function useLegendTool({ projectId, countTypes, pagesRef, onCreate }) {
  const [s, setS] = useState(EMPTY);
  const runRef = useRef(0);
  const set = (patch) => setS((cur) => ({ ...cur, ...(typeof patch === 'function' ? patch(cur) : patch) }));

  const count = async (rows, run, legends) => {
    set({ phase: 'counting', legends, rows, counts: {}, review: {}, removed: new Set(), notice: null, reuse: null });
    const countable = rows.filter((r) => r.countable !== false);
    let counts = {};
    try {
      if (countable.length) {
        const res = await countLegendRows(projectId, countable);
        if (run !== runRef.current) return;
        counts = Object.fromEntries((res.rows || []).map((r) => [r.row_id, r]));
      }
    } catch (e) {
      if (run !== runRef.current) return;
      toast.error(`Ženklų suskaičiuoti nepavyko: ${e?.message || 'klaida'}`, { description: 'Eilutes vis tiek galite peržiūrėti ir pažymėti ženklus rankiniu būdu.' });
    }
    for (const r of rows) {
      if (!counts[r.row_id]) {
        counts[r.row_id] = { row_id: r.row_id, status: r.countable === false ? 'neskaiciuojama' : 'klaida', count: 0, instances: [], kiti: [], per_page: [],
          sentence_lt: r.reason_lt || 'Šios eilutės ženklų suskaičiuoti nepavyko — pažymėkite juos rankiniu būdu.' };
      }
    }
    if (run !== runRef.current) return;
    set({ phase: 'review', counts, review: initialReview(rows, counts) });
    const reuse = await findReuse(projectId, rows);
    if (run !== runRef.current || !reuse) return;
    set({ reuse });
  };

  const suggest = async (page) => {
    const run = ++runRef.current;
    set({ ...EMPTY, architect: s.architect, phase: 'suggesting', page });
    try {
      const res = await fetchLegendRows(projectId, { page });
      if (run !== runRef.current) return;
      const proposals = proposalsFrom(res);
      if (proposals.length) set({ phase: 'proposed', proposals, notice: res.detail || null });
      else set({ phase: 'box', notice: 'Šiame lape legendos neradau — apveskite ją rėmeliu' });
    } catch (e) {
      if (run !== runRef.current) return;
      set({ phase: 'box', notice: e?.message ? `Legendos pasiūlyti nepavyko — apveskite ją rėmeliu (${e.message})` : 'Apveskite legendą rėmeliu' });
    }
  };

  const open = (page) => { suggest(page || 1); };
  const close = () => { runRef.current += 1; setS((cur) => ({ ...EMPTY, architect: cur.architect })); };

  // He scrolled to another sheet before choosing: propose that sheet's legend instead.
  const pageShown = (page) => {
    if (!page || page === s.page) return;
    if (s.phase === 'proposed' || (s.phase === 'box' && !s.rows.length)) suggest(page);
  };

  const accept = (proposalId = null) => {
    if (s.phase !== 'proposed') return;
    const legends = proposalId ? s.proposals.filter((p) => p.id === proposalId) : s.proposals;
    const rows = rowsOf(legends);
    if (!rows.length) return;
    const run = ++runRef.current;
    count(rows, run, legends);
  };

  const redraw = () => {
    runRef.current += 1;
    set({ phase: 'box', proposals: [], legends: [], rows: [], counts: {}, review: {}, removed: new Set(), notice: null, reuse: null });
  };

  const box = async (page, bboxPct) => {
    if (!bboxPct) { flashCursorHint('Rėmelis per mažas — apveskite visą legendą'); return; }
    const run = ++runRef.current;
    set({ phase: 'reading', page, proposals: [], notice: null });
    try {
      const res = await fetchLegendRows(projectId, { page, bboxPct });
      if (run !== runRef.current) return;
      const rows = res.rows || [];
      if (!rows.length) {
        set({ phase: 'box', notice: res.detail || 'Rėmelyje legendos eilučių neradau — apveskite ženklus kartu su jų pavadinimais' });
        return;
      }
      count(rows, run, [{ id: `${page}:remelis`, page, bbox_pct: bboxPct, rows }]);
    } catch (e) {
      if (run !== runRef.current) return;
      set({ phase: 'box', notice: e?.message || 'Eilučių perskaityti nepavyko' });
    }
  };

  const setKeep = (rowId, keep) => set((cur) => ({ review: { ...cur.review, [rowId]: { ...(cur.review[rowId] || {}), keep } } }));
  const rename = (rowId, name) => set((cur) => ({ review: { ...cur.review, [rowId]: { ...(cur.review[rowId] || {}), name } } }));
  const removeInstance = (id) => set((cur) => {
    const removed = new Set(cur.removed);
    removed.add(id);
    return { removed, hoveredId: cur.hoveredId === id ? null : cur.hoveredId };
  });
  const restoreRow = (rowId) => set((cur) => ({ removed: new Set([...cur.removed].filter((id) => !id.startsWith(`${rowId}#`))) }));
  const setHovered = (id) => set({ hoveredId: id });
  const setHoveredRow = (rowId) => set({ hoveredRowId: rowId });
  const setArchitect = (architect) => set({ architect });
  const applyReuse = () => set((cur) => (cur.reuse
    ? { review: { ...cur.review, ...cur.reuse.review }, architect: cur.architect || cur.reuse.architect || '', reuse: { ...cur.reuse, applied: true } }
    : {}));
  const dismissReuse = () => set({ reuse: null });

  const toCreate = useMemo(() => rowsToCreate(s.rows, s.review, s.counts, s.removed), [s.rows, s.review, s.counts, s.removed]);
  const blanks = useMemo(() => blankRows(s.rows, s.review, s.counts, s.removed), [s.rows, s.review, s.counts, s.removed]);

  const create = async () => {
    if (s.phase !== 'review' || !(toCreate.length || blanks.length)) return;
    const pages = pagesRef.current || [];
    const plan = buildCreate({ rows: s.rows, counts: s.counts, review: s.review, removed: s.removed, countTypes, pages });
    const snapshot = s;
    set({ phase: 'creating' });
    let previous = null;
    try { previous = await loadProjectLegend(projectId); } catch { previous = null; }
    const undoLegend = () => { saveProjectLegend(projectId, previous || { rows: [] }).catch(() => {}); };
    const architect = String(snapshot.architect || '').trim();
    const undoMarks = onCreate(plan, { label: `Sukurta pagal legendą: ${plan.made.length} kiek., ${plan.marks.length} žym.${plan.blanks.length ? `, ${plan.blanks.length} tuščios eil.` : ''}`, undoLegend });
    // the legend this project keeps (rows he kept, his names), and the reuse on his next project
    const savedRows = legendRowsToSave(snapshot.rows, snapshot.review);
    const keepOld = (previous?.rows || []).filter((r) => !savedRows.some((n) => n.row_id === r.row_id));
    saveProjectLegend(projectId, { rows: [...keepOld, ...savedRows], symbols: previous?.symbols || [], architect: architect || previous?.architect || null })
      .then(() => {
        if (!architect) return;
        const all = rememberArchitect(architect, projectId);
        const others = (all[architect] || []).filter((p) => p !== projectId);
        if (others.length) promoteArchitectLegend(projectId, architect, [projectId, ...others.slice(-4)]).catch(() => {});
      })
      .catch(() => toast.warning('Legenda neišsaugota kitam kartui — kiekiai sukurti'));
    // the corpus and the journal: every row he judged, every mark he removed (fire-and-forget)
    const typeOf = new Map(plan.made.map((m) => [m.row.row_id, m.type]));
    sendLegendLearning(projectId, {
      journal: journalRows(snapshot),
      decisions: decisionsFor({ ...snapshot, pages, klassOf: (row) => klassFor(typeOf.get(row.row_id) || { id: row.text }) }),
    }).then((failed) => { if (failed) toast.warning(`Mokymo duomenų įrašyti nepavyko (${failed})`); });
    close();
    return undoMarks;
  };

  const instancesOn = useCallback((page) => {
    const out = [];
    for (const row of s.rows) {
      const c = s.counts[row.row_id];
      if (!c) continue;
      (c.instances || []).forEach((inst, i) => {
        const id = instanceId(row.row_id, i);
        if (inst.page === page && !s.removed.has(id)) out.push({ ...inst, id, rowId: row.row_id, keep: !!s.review[row.row_id]?.keep });
      });
    }
    return out;
  }, [s.rows, s.counts, s.removed, s.review]);

  return {
    ...s, active: s.phase != null, toCreate, blanks, open, close, pageShown, accept, redraw, box, setKeep, rename,
    removeInstance, restoreRow, setHovered, setHoveredRow, setArchitect, applyReuse, dismissReuse, create, instancesOn,
  };
}

/**
 * One page's legend overlay, in DISPLAY-frame fractions × the rendered size (the frame the legend routes
 * answer in). It owns the pointer while the tool is on.
 */
export function LegendLayer({ page, width, height, legend }) {
  const svgRef = useRef(null);
  const [drag, setDrag] = useState(null);
  const phase = legend.phase;
  const canDraw = phase === 'proposed' || phase === 'box';
  const pct = (e) => {
    const r = svgRef.current?.getBoundingClientRect();
    if (!r || !r.width || !r.height) return null;
    return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height };
  };
  const rect = (b) => ({ x: b[0] * width, y: b[1] * height, w: (b[2] - b[0]) * width, h: (b[3] - b[1]) * height });

  const onPointerDown = (e) => {
    if (e.button !== 0 || !canDraw) return;
    const p = pct(e);
    if (!p) return;
    e.preventDefault();
    e.stopPropagation();
    svgRef.current?.setPointerCapture?.(e.pointerId);
    setDrag({ a: p, b: p });
  };
  const onPointerMove = (e) => {
    if (!drag) return;
    const p = pct(e);
    if (p) setDrag((d) => (d ? { ...d, b: p } : d));
  };
  const onPointerUp = (e) => {
    if (!drag) return;
    e.stopPropagation();
    svgRef.current?.releasePointerCapture?.(e.pointerId);
    const p = pct(e) || drag.b;
    const moved = Math.abs(p.x - drag.a.x) * width + Math.abs(p.y - drag.a.y) * height;
    setDrag(null);
    if (moved < 6) {
      // a click: on a proposal it is „Taip" for that legend
      const hit = phase === 'proposed' && legend.page === page ? legend.proposals.find((pr) => pointInBox(pr.bbox_pct, p.x, p.y)) : null;
      if (hit) legend.accept(hit.id);
      else flashCursorHint(phase === 'proposed' ? 'Čia legendos nėra — spustelėkite pasiūlytą rėmelį arba tempkite savo' : 'Tempkite — apveskite visą legendą');
      return;
    }
    legend.box(page, boxFromPctDrag(drag.a, p));
  };

  const PROPOSED = ov('proposed');
  const READ = ov('read');
  const showProposals = phase === 'proposed' && legend.page === page ? legend.proposals : [];
  const accepted = phase && phase !== 'proposed' ? legend.legends.filter((l) => l.page === page) : [];
  const instances = phase === 'review' || phase === 'counting' ? legend.instancesOn(page) : [];
  const dragBox = drag ? boxFromPctDrag(drag.a, drag.b, 0) : null;
  const tag = (x, y, text, colour) => {
    const w = labelWidth(text);
    return (
      <g pointerEvents="none">
        <rect x={x} y={y - 19} width={w} height={17} rx={2} style={paint({ fill: ov('label-bg'), stroke: colour })} fillOpacity={0.96} strokeWidth={1} />
        <text x={x + 7} y={y - 6} fontSize={LABEL_FONT_PX} fontWeight={500} style={{ ...LABEL_STYLE, ...paint({ fill: ov('label-fg') }) }}>{text}</text>
      </g>
    );
  };

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      style={{ position: 'absolute', inset: 0, cursor: canDraw ? 'crosshair' : 'default', touchAction: 'none' }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => setDrag(null)}
      data-testid={`legend-layer-${page}`}
    >
      {showProposals.map((pr) => {
        const r = rect(pr.bbox_pct);
        return (
          <g key={pr.id} data-testid="legend-proposal" style={{ cursor: 'pointer' }}>
            <title>Siūloma legenda ({pr.rows.length} eil.) — spustelėkite, jei tai ji</title>
            <rect x={r.x - 3} y={r.y - 3} width={r.w + 6} height={r.h + 6} style={paint({ fill: PROPOSED, stroke: PROPOSED })} fillOpacity={0.10} strokeWidth={STROKE_PX} strokeDasharray={DASH} />
            {tag(r.x - 3, r.y - 5, `Tai legenda? · ${pr.rows.length} eil.`, PROPOSED)}
          </g>
        );
      })}
      {accepted.map((l) => {
        const r = rect(l.bbox_pct);
        return (
          <g key={l.id} pointerEvents="none" data-testid="legend-accepted">
            <rect x={r.x - 3} y={r.y - 3} width={r.w + 6} height={r.h + 6} fill="none" style={paint({ stroke: READ })} strokeWidth={STROKE_PX} />
            {tag(r.x - 3, r.y - 5, 'Legenda', READ)}
          </g>
        );
      })}
      {instances.map((inst) => {
        const r = rect(inst.box_pct);
        const hot = inst.id === legend.hoveredId || inst.rowId === legend.hoveredRowId;
        const pad = 3;
        return (
          <g
            key={inst.id}
            style={{ cursor: 'pointer' }}
            opacity={inst.keep ? 1 : 0.45}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => { e.stopPropagation(); legend.removeInstance(inst.id); }}
            onPointerEnter={() => legend.setHovered(inst.id)}
            onPointerLeave={() => legend.setHovered(null)}
            data-testid="legend-instance"
          >
            <title>Rasta pagal legendą — spustelėkite, jei tai ne tas ženklas (pašalinti)</title>
            <rect x={r.x - pad} y={r.y - pad} width={Math.max(8, r.w + pad * 2)} height={Math.max(8, r.h + pad * 2)}
              style={paint({ fill: ov('label-bg'), stroke: PROPOSED })} fillOpacity={hot ? 0.5 : 0.15}
              strokeWidth={hot ? 3 : STROKE_PX} strokeDasharray={DASH} />
          </g>
        );
      })}
      {dragBox && (() => {
        const r = rect(dragBox);
        return <rect x={r.x} y={r.y} width={r.w} height={r.h} style={paint({ fill: ov('editing'), stroke: ov('editing') })} fillOpacity={0.08} strokeWidth={1.5} pointerEvents="none" />;
      })()}
    </svg>
  );
}
