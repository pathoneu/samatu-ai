/**
 * InteriorWorkspace — the project's ONE workspace (Pathon v3, design §3; wave-1 track A).
 *
 *   ┌──────────────────────────────────────────┬────────────────────────────┐
 *   │                                          │  RIGHT PANEL (mode host)   │
 *   │   THE DRAWING (TakeoffViewer)            │  Patalpos ir eilutės ·     │
 *   │   mounted once, kept across all views    │  Kiekiai · Patikra ·       │
 *   │                                          │  Sąmata · Pokalbis         │
 *   └──────────────────────────────────────────┴────────────────────────────┘
 *
 * The four steps are views of this one component (lib/workspaceViews):
 *   brezinys — the drawing takes the width, the panel 340 px (resizable, remembered);
 *   patikra  — the drawing beside a wide panel with the question list / room sheet;
 *   samata   — the drawing beside the rows; „Išskleisti" collapses the drawing to a 56 px strip;
 *   siusti   — its own screen; the drawing waits behind the strip.
 * The viewer is never unmounted by a step change: its zoom, page, measurements and history survive,
 * and the PDF engine loads once. Behind the strip it keeps its last size and stops listening to keys.
 */

import { useState, useMemo, useEffect, useRef, useCallback, lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Layers, Upload, Map as MapIcon, Maximize2, Minimize2 } from 'lucide-react';
import PlanViewer from './PlanViewer';
import TakeoffViewer from '@/components/viewer/TakeoffViewer';
import DetectRunButton from '@/components/viewer/DetectRunButton';
import RevisionCompareControl from '@/components/viewer/RevisionCompareControl';
import DetectRunProgress from '@/components/viewer/DetectRunProgress';
import { useDetectRun } from '@/lib/useDetectRun';
import WorkspacePanel from './WorkspacePanel';
import MobileViewOnlyBanner from './MobileViewOnlyBanner';
import RightPanelHost from './RightPanelHost';
import { WorkspaceHostContext } from './workspaceHost';
import { toast } from 'sonner';
import { sheetsCrossingLimit, sheetLimitMessage } from '@/lib/measureLimits';
import { getPdfUrl, getPdfBlob, savePdf, uploadPdfToBackend } from '@/lib/pdfStore';
import { laneScalesOf } from '@/lib/durableScale';
import { getProject, updateProject, flushProjectSaves } from '@/lib/projectStore';
import { buildPageMetaDict, firstPlanPage, missingInteriorTypes } from '@/lib/pageTypes';
import { detectRoomPolygons } from '@/lib/detectRoomPolygonsApi';
import { fetchOutlineAt, fetchOutlineMerge, fetchOutlineSet, restoreOutline } from '@/lib/roomOutlineApi';
import { isNewest, newerSaves, restorePatch, ticketFor, undoneRooms, undoneSentence, UNDO_SUPERSEDED } from '@/lib/outlineUndo';
import { roomsWithOutline } from '@/lib/roomOutline';
import { saveOutlineTool } from '@/lib/outlineToolSave';
import {
  MIN_SPLIT_CANVAS, PANEL_LIMITS, PANEL_TABS, STRIP_WIDTH, canvasModeForView, panelWidthFor, readPanelWidth,
  revealTarget, selectTab, tabForView, writePanelWidth,
} from '@/lib/workspaceViews';
import QuantitiesPanel from '@/components/viewer/quantities/QuantitiesPanel';
import AiChat from '@/components/project/AiChat';
import { syncLegendRows } from '@/lib/legendReview';
import { legendCounts } from '@/lib/legendCounts';
import { withZoneSheetTypes } from '@/lib/sheetRail';

// Patikra's question list / room sheet (its own chunk, as when it was a separate route).
const PatikraEntry = lazy(() => import('@/pages/PatikraEntry'));

// Outlines that must never be re-detected over. The last two are traced by the
// BACKEND during extraction (wall_outline.py, vector_rooms.py): before
// 2026-09-19 they were missing here, so the first time a project was opened
// the browser's flood-fill ran anyway and replaced them — objektas_h's eight
// wall-exact outlines came back as `manual_needed` with no polygon at all.
const DETECTED_SOURCES = ['auto_floodfill', 'corrected', 'manual', 'manual_needed',
  'sienu_konturas', 'vektoriniai_konturai'];

// Apply a per-room field patch (keyed by nr) to BOTH patalpos and v8_rooms so
// the two room arrays the app reads (`v8_rooms || patalpos`) never diverge.
//
// Returns ONLY the room arrays — field-scoped by design (2026-07-27 audit).
// The previous version returned a whole `{...project}` spread, so an async
// continuation (polygon auto-detect, click-to-fill) republished the project as
// it looked when the work STARTED and silently reverted every price edit,
// measurement and second-tab write that landed in the meantime.
function roomPatchFields(source, patchByNr) {
  const patch = (arr) => (arr || []).map((r) => {
    const p = patchByNr[String(r.nr)];
    return p ? { ...r, ...p } : r;
  });
  return {
    patalpos: patch(source.patalpos),
    ...(Array.isArray(source.v8_rooms) && { v8_rooms: patch(source.v8_rooms) }),
  };
}

const SYMBOL_LABELS = {
  rozetes: 'Rozetės / jungiklio pajungimas',
  jungikliai: 'Rozetės / jungiklio pajungimas',
  sviestuvai: 'Lubinių priglaistomų šviestuvų apdirbimas',
  pakabinami_sviestuvai: 'Pakabinamų šviestuvų montavimas',
  difuzoriai: 'Difūzorių apdirbimas (ventiliacijos taškai)',
  klozetai: 'Klozeto montavimas',
  praustuvai: 'Praustuvų montavimas',
  vonios: 'Vonios montavimas',
  trapai: 'Linijinio latako montavimas (vonios drenažas)',
  maisytuvai: 'Maišytuvų montavimas',
  gyvatukai: 'Gyvatuko (rankšluosčių džiovintuvo) montavimas',
  durys: 'Durys (vidaus)',
  langai: 'Langai',
  template_symbol: 'Sutartinis ženklas (paspaudimu)',
  led_juostos: 'LED juostos / nišos',
  skalbimo_masinos: 'Skalbimo mašinos prijungimas',
  radiatoriai: 'Radiatoriai',
};

const SYMBOL_CATEGORIES = {
  rozetes: 'Elektra',
  jungikliai: 'Elektra',
  sviestuvai: 'Apšvietimas',
  pakabinami_sviestuvai: 'Apšvietimas',
  difuzoriai: 'Ventiliacija',
  klozetai: 'Santechnika',
  praustuvai: 'Santechnika',
  vonios: 'Santechnika',
  trapai: 'Santechnika',
  maisytuvai: 'Santechnika',
  gyvatukai: 'Santechnika',
  durys: 'GKP',
  langai: 'GKP',
  template_symbol: 'Sutartiniai ženklai',
  led_juostos: 'Apšvietimas',
  skalbimo_masinos: 'Santechnika',
  radiatoriai: 'Šildymas',
};

// Viewer engine: the new EmbedPDF TakeoffViewer is now the DEFAULT. Opt back into
// the legacy react-pdf PlanViewer with ?viewer=legacy (or localStorage
// samatu_viewer_engine=legacy) — kept as a one-flag safety net until the remaining
// tools (click-to-fill, symbol-count) are re-homed and parity is confirmed.
//
// ⚠️ ?viewer=legacy is a RENDER-ONLY escape hatch ("the new viewer won't draw
// my PDF"), NOT a feature-equivalent alternative. Verified against
// PlanViewer.jsx 2026-07-27 — compared with TakeoffViewer it has NO:
//   - measurement authoring at all: no distance/perimeter/area/count tools, no
//     scale calibration, no user-defined count types / CountLegendPanel, and
//     no initialMeasurements/onMeasureDataChange wiring, so nothing it does can
//     reach the Matavimai list or its CSV/JSON export
//   - fillRequest arming — the review-queue pencil ("Taisyti zoną",
//     handleEditRoomZone below) is consumed only by TakeoffViewer, so in legacy
//     mode that button focuses the room and then silently does nothing. Legacy
//     has its own separate in-toolbar click-to-fill; it is not the same path.
//   - hidden-room / hovered-room sync with the workspace panel
//     (hiddenRoomNrs + hoveredRoomNrExternal are TakeoffViewer-only props)
//   - the room-zone fill toggle (zoneFillsVisible)
// It does keep PDF render, room-zone click→focus and AI symbol counting
// (onSymbolCountResult). Treat any bug report from this mode as "reproduce on
// the default viewer first".
function viewerEngineIsEmbed() {
  try {
    const q = new URLSearchParams(window.location.search).get('viewer');
    if (q === 'legacy') return false;
    if (q === 'embed') return true;
    return localStorage.getItem('samatu_viewer_engine') !== 'legacy';
  } catch { return true; }
}

export default function InteriorWorkspace({
  project,
  // Which of the four steps is on screen (lib/workspaceViews VIEWS). The drawing is the same in all of
  // them; the view decides how much of the width it gets and what the right panel shows.
  view = 'brezinys',
  focusedPage = null,
  focusedRoom = null,
  onJumpToPage = null,
  onProjectChange = null,
  // Patikra (2026-09-02): „Pataisyti" has to land on the control that produced
  // the wrong number, so the jump carries {field, roomNr} through to Prielaidos.
  onOpenAssumptions = null,
  // …and the recompute it triggers comes back as a visible € ripple.
  lastRipple = null,
  // (view) => void — a panel tab or the drawing strip asks for another step.
  onViewChange = null,
  // Sąmata „Išskleisti": the rows take the width, the drawing a strip.
  samataExpanded = false,
  onSamataExpandedChange = null,
  // (project) => void — Patikra's panel keeps its own copy of the project while he answers.
  onPatikraProject = null,
  // The Sąmata rows (ProjectMainView) and the Siųsti screen — owned by the project page.
  samataContent = null,
  sendContent = null,
  // Notices (re-read summary, free re-read offer) — shown above the panel, never in the drawing's column.
  notices = null,
  className = '',
}) {
  const { t } = useTranslation();
  // „Perskaityti lapą" (2026-10-16): the €0 reading per sheet with named stages (api/detect_run.py)
  const detectRun = useDetectRun(project, onProjectChange);
  // „Palyginti leidimus“ (togal-v2 W10): a later edition laid over the sheets — on screen only, never saved
  const [revisionOverlay, setRevisionOverlay] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [pdfBlob, setPdfBlob] = useState(null);  // Diena 6: V9 click-to-count'ui
  const [pdfMissing, setPdfMissing] = useState(false);
  const [attachingPdf, setAttachingPdf] = useState(false);
  // Local override: when user clicks a room in the right-side panel while
  // already on this view, bump local focused page/room (in addition to
  // bubbling up). Prop changes take priority — local override resets on prop.
  const [localFocusedPage, setLocalFocusedPage] = useState(null);
  // Sentinel semantics (audit P2 "sticky chip"): undefined = no local override
  // (parent focus applies), null = user EXPLICITLY cleared focus (blank-canvas
  // click / Esc) — must win over a still-set parent focusedRoom.
  const [localFocusedRoom, setLocalFocusedRoom] = useState(undefined);
  // Phase 1 declutter (2026-07-02): panel-driven per-room canvas visibility.
  // Set of String(nr) hidden from the canvas + the panel-row hover that
  // brightens the matching zone (panel → canvas half of the hover sync).
  const [hiddenRoomNrs, setHiddenRoomNrs] = useState(() => new Set());
  const [hoveredRoomNr, setHoveredRoomNr] = useState(null);
  // Right panel tab (Togal-v2 capability B; v3 mode host): the drawing view keeps the tab he last chose
  // there ('patalpos' | 'kiekiai' | 'pokalbis'); Patikra and Sąmata show their own. The drawing tabs stay
  // mounted while hidden so their filters / folds survive a switch.
  const [drawingTab, setDrawingTab] = useState('patalpos');
  // „Pažymėti legendą" (v3 W2-B): while the tool is on, its review covers the right panel (the tabs stay mounted)
  const [legendOpen, setLegendOpen] = useState(false);
  const [legendSlot, setLegendSlot] = useState(null);
  const rightTab = tabForView(view, drawingTab);
  const setRightTab = useCallback((tab) => {
    const next = selectTab(view, tab);
    if (next.view === 'brezinys') setDrawingTab(next.tab);
    if (next.view !== view) onViewChange?.(next.view);
  }, [view, onViewChange]);
  // „Pokalbis" (togal-v2 W11): the line selected in Kiekiai is offered to the chat; „Pridėti į pokalbį" adds one.
  const [kiekiaiActiveRow, setKiekiaiActiveRow] = useState(null);
  const [chatAddRequest, setChatAddRequest] = useState(null);
  // Open on the first PLAN page. Page 1 of a real interior set is a marketing
  // render whose scale reads „nekalibruotas"; the plan on page 2 auto-seeds its
  // own scale. Landing on the cover asks the contractor to work out that the
  // app opened the wrong page before he has done anything. (Design §4.)
  const defaultPage = useMemo(() => firstPlanPage(project), [project.puslapiai, project.v8_pages, project.patalpos]);
  const effectiveFocusedPage = localFocusedPage ?? focusedPage ?? defaultPage;
  // Re-derive the focused room from the LIVE patalpos by nr — the focusedRoom
  // prop / local state is a captured object and can carry a stale polygon after
  // auto-detect upgrades the room's polygon_pct. Always render the latest.
  const rawFocusedRoom = localFocusedRoom === undefined ? focusedRoom : localFocusedRoom;
  const effectiveFocusedRoom = rawFocusedRoom
    ? ((project.v8_rooms || project.patalpos || []).find(
        (r) => String(r.nr) === String(rawFocusedRoom.nr)) || rawFocusedRoom)
    : null;
  useEffect(() => {
    setLocalFocusedPage(null);
    setLocalFocusedRoom(undefined);
  }, [focusedPage, focusedRoom]);

  useEffect(() => {
    let revoked = false;
    let url = null;
    Promise.all([getPdfUrl(project.id), getPdfBlob(project.id)])
      .then(([u, b]) => {
        if (!revoked) {
          url = u;
          setPdfUrl(u);
          setPdfBlob(b);
          setPdfMissing(!u);
        } else if (u) {
          URL.revokeObjectURL(u);
        }
      })
      .catch((e) => {
        // NO .catch here was a blank-screen dead end (2026-07-28 audit): a
        // rejected IndexedDB read / backend fetch left pdfMissing false, so the
        // pane sat on "Kraunamas brėžinys…" forever and the "Įkelti brėžinį"
        // recovery UI — which is exactly what the user needs then — was
        // unreachable without a reload.
        console.warn('[InteriorWorkspace] PDF load failed:', e);
        if (!revoked) setPdfMissing(true);
      });
    return () => {
      revoked = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [project.id]);

  // Accurate room polygons: once the PDF is available, replace the coarse bbox
  // polygons with wall-following flood-fill ones (label-seeded + area-prior).
  // Runs ONCE per project (skips if rooms already carry a detected source).
  const [detecting, setDetecting] = useState(false);
  const detectRanRef = useRef(false);
  useEffect(() => {
    // 2026-06-17 (founder): auto flood-fill polygons disabled — the viewer showed
    // a clean room-number marker (centred on the existing room rect), not an
    // auto-traced boundary.
    // 2026-07-02: re-enabled after the multi-seed accuracy lift (label seed +
    // bbox-centroid) + seed-inside-polygon guard + ground-truth benchmark gate
    // (Phase A: Objektas A auto >= 8, wrong_room_fills = 0 on every project). The
    // detector now traces walls where confident and emits a label-anchored
    // marker_pct where it can't — never a fabricated coarse rectangle.
    const AUTO_DETECT_POLYGONS = true;
    if (!AUTO_DETECT_POLYGONS) return;
    if (!pdfBlob || detectRanRef.current) return;
    const rooms = project.v8_rooms || project.patalpos || [];
    if (rooms.length === 0) return;
    // Skip if EITHER array already carries a detected source (don't re-run and
    // overwrite a user's manual correction).
    const alreadyDetected = [...(project.patalpos || []), ...(project.v8_rooms || [])]
      .some((r) => DETECTED_SOURCES.includes(r.polygon_source));
    if (alreadyDetected) {
      detectRanRef.current = true;
      return;
    }
    detectRanRef.current = true;
    setDetecting(true);
    (async () => {
      try {
        const byPage = {};
        rooms.forEach((r) => {
          const p = r.puslapio_nr ?? r.page_nr;
          if (p) (byPage[p] = byPage[p] || []).push(r);
        });
        const merged = {};
        for (const [pageNr, pageRooms] of Object.entries(byPage)) {
          const { results } = await detectRoomPolygons({
            projectId: project.id, pageNr: Number(pageNr), rooms: pageRooms, pdfBlob,
          });
          Object.assign(merged, results);
        }
        const patchByNr = {};
        for (const [nr, res] of Object.entries(merged)) {
          patchByNr[nr] = res.polygon_pct
            ? {
              polygon_pct: res.polygon_pct,
              polygon_pdf: res.polygon_pdf,
              page_width_pdf: res.page_width_pdf,
              page_height_pdf: res.page_height_pdf,
              polygon_source: res.polygon_source,
              polygon_confidence: res.confidence,
              area_err: res.area_err,
              marker_pct: res.marker_pct ?? null,
              marker_source: res.marker_source ?? null,
            }
            // No polygon → CLEAR stale geometry fields too (contract audit
            // 2026-07-12: 6 rooms across 3 projects carried manual_needed
            // plus a leftover fabricated rect that any new reader would
            // mistake for real geometry).
            : {
              polygon_source: res.polygon_source,
              polygon_pct: null,
              polygon_pdf: null,
              polygon_confidence: null,
              area_err: null,
              marker_pct: res.marker_pct ?? null,
              marker_source: res.marker_source ?? null,
            };
        }
        // Re-read the CURRENT stored project — detection takes seconds and the
        // user keeps working while it runs.
        const fresh = getProject(project.id) || project;
        const updated = updateProject(project.id, roomPatchFields(fresh, patchByNr));
        if (updated) onProjectChange?.(updated);
      } catch (e) {
        console.warn('[detect-room-polygons] failed:', e?.message);
      } finally {
        setDetecting(false);
      }
    })();
  }, [pdfBlob, project.id]);   

  // Review-queue pencil → focus the room, jump to its plan page AND arm
  // click-to-fill in the viewer (fillRequest is consumed by TakeoffViewer;
  // t is a nonce so re-clicking the same pencil re-arms after Esc).
  const [fillRequest, setFillRequest] = useState(null);
  const handleEditRoomZone = (room) => {
    if (!room?.nr) return;
    if (room.puslapio_nr) setLocalFocusedPage(room.puslapio_nr);
    setLocalFocusedRoom(room);
    setFillRequest({ nr: room.nr, t: Date.now() });
  };

  // Manual fix: persist a click-to-fill polygon as the focused room's accurate
  // contour (polygon_source 'corrected'). Clears the manual_needed flag.
  const handleRoomPolygonFill = (roomNr, fill) => {
    if (!roomNr || !fill?.polygon_pdf?.length) return;
    const pw = fill.page_width_pdf, ph = fill.page_height_pdf;
    const polygon_pct = (pw && ph)
      ? fill.polygon_pdf.map(([x, y]) => [x / pw, y / ph]) : null;
    const patch = {
      ...(polygon_pct && { polygon_pct }),
      polygon_pdf: fill.polygon_pdf,
      page_width_pdf: pw,
      page_height_pdf: ph,
      polygon_source: 'corrected',
      polygon_confidence: fill.confidence || 'high',
      polygon_corrected_at: new Date().toISOString(),
    };
    const fresh = getProject(project.id) || project;
    // „Atšaukti" (Pathon v3 W1-D): the raster fill is saved in the browser alone, so its undo is too — the
    // room's polygon keys as they were (null where it had none).
    const before = (fresh.patalpos || []).find((r) => String(r?.nr) === String(roomNr)) || {};
    const restore = Object.fromEntries(Object.keys(patch).concat('polygon_pct').map((k) => [k, before[k] ?? null]));
    const ticket = ticketFor(undoRegistryRef.current, [String(roomNr)]);
    const updated = updateProject(project.id, roomPatchFields(fresh, { [String(roomNr)]: patch }));
    if (updated) onProjectChange?.(updated);
    return {
      undo: () => {
        if (!isNewest(undoRegistryRef.current, ticket)) { toast.info(UNDO_SUPERSEDED); return; }
        ticketFor(undoRegistryRef.current, [String(roomNr)]);
        const now = getProject(project.id) || project;
        const back = updateProject(project.id, roomPatchFields(now, { [String(roomNr)]: restore }));
        if (back) onProjectChange?.(back);
        toast.success(`Atšaukta: patalpos ${roomNr} kontūras grąžintas`);
      },
    };
  };

  // „Atšaukti" after every outline save (Pathon v3 W1-D, D3): the server's answer carries `previous`; the undo
  // PUTs it back through the same route and lands the answer like the save, then the sheet recomputes. An
  // older save of a room is not undone after a newer one (it would drop the newer one).
  const undoRegistryRef = useRef(newerSaves());
  const makeOutlineUndo = ({ action, nr, previous } = {}) => {
    if (!previous || !Object.keys(previous).length) return null;
    const ticket = ticketFor(undoRegistryRef.current, undoneRooms(previous));
    return async () => {
      if (!isNewest(undoRegistryRef.current, ticket)) { toast.info(UNDO_SUPERSEDED); return; }
      try {
        await flushProjectSaves().catch(() => null);
        const answer = await restoreOutline(project.id, nr, action, previous);
        const patch = restorePatch(getProject(project.id) || project, answer);
        if (!patch) throw new Error('Atšaukti nepavyko');
        ticketFor(undoRegistryRef.current, undoneRooms(previous));      // the undo is now the newest change
        const updated = updateProject(project.id, patch);
        if (updated) onProjectChange?.(updated);
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('samatu:project-recompute', {
            detail: { projectId: project.id, reason: 'outline-undone', roomNr: nr, quiet: true },
          }));
        }
        toast.success(undoneSentence(action, previous), { description: 'Kiekiai perskaičiuojami.' });
      } catch (e) {
        toast.error(e?.userMessage || e?.message || 'Atšaukti nepavyko');
      }
    };
  };

  // Outline edited vertex by vertex in the viewer (2026-10-16): the server measures the ring, reads its
  // walls and openings again (api/room_outline.py outline-set) and answers geometry keys only;
  // roomsWithOutline applies them to the rooms and nothing else. Saving dispatches
  // samatu:project-recompute, which InteriorProject routes through /recompute-interior — the one path
  // every other room edit takes.
  const landOutlineAnswer = (roomNr, answer, reason) => {
    const fresh = getProject(project.id) || project;
    const rooms = roomsWithOutline(fresh, roomNr, answer);
    if (!rooms) throw new Error(typeof answer?.detail === 'string' ? answer.detail : 'Kontūras nepriimtas');
    const patch = { patalpos: rooms };
    if (Array.isArray(fresh.v8_rooms)) {
      const byNr = new Map(rooms.map((r) => [String(r?.nr), r]));
      patch.v8_rooms = fresh.v8_rooms.map((r) => byNr.get(String(r?.nr)) || r);
    }
    const updated = updateProject(project.id, patch);
    if (updated) onProjectChange?.(updated);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('samatu:project-recompute', {
        // quiet: the save's own toast says the quantities are being recomputed and holds its „Atšaukti"
        detail: { projectId: project.id, reason, roomNr, quiet: true },
      }));
    }
  };
  const handleRoomOutlineEdit = async (roomNr, page, points, holes = null) => {
    await flushProjectSaves().catch(() => null);
    const answer = await fetchOutlineSet(project.id, roomNr, { page, polygon_pct: points, holes });
    landOutlineAnswer(roomNr, answer, 'outline-edited');
    return { undo: makeOutlineUndo({ action: 'outline-set', nr: String(roomNr), previous: answer?.previous }) };
  };

  // The viewer's room tool R (Pathon v3 W1-D): one click → the wall-exact outline PROPOSED (outline-at with
  // `perziura` — read, nothing saved, no journal row), then saved once he has seen it through outline-set
  // (`kaip: 'parodyta'`) — the walls and openings read again and the sheet recomputed on the same path as
  // every outline save. The stored project is brought up to date first, so the server reads what he sees.
  const handleRoomToolPreview = async (roomNr, point) => {
    await flushProjectSaves().catch(() => null);
    return fetchOutlineAt(project.id, roomNr, point, { perziura: true });
  };
  const handleRoomToolCommit = async (roomNr, body) => {
    await flushProjectSaves().catch(() => null);
    const answer = await fetchOutlineSet(project.id, roomNr, body);
    landOutlineAnswer(roomNr, answer, 'outline-pointed');
    return { undo: makeOutlineUndo({ action: 'outline-set', nr: String(roomNr), previous: answer?.previous }) };
  };

  // Outline tools (2026-10-16): „Padalyti" / „Sujungti" / „Atimti" — lib/outlineToolSave builds ONE patch
  // from the server's answers, then the sheet recomputes once on the usual path.
  const handleOutlineTool = async (op) => {
    await flushProjectSaves().catch(() => null);
    let undoable = null;
    const patch = await saveOutlineTool(op, {
      api: {
        outlineSet: (nr, body) => fetchOutlineSet(project.id, nr, body),
        outlineMerge: (nr, body) => fetchOutlineMerge(project.id, nr, body),
      },
      getFresh: () => getProject(project.id) || project,
      onPrevious: (u) => { undoable = u; },
    });
    const updated = updateProject(project.id, patch);
    if (updated) onProjectChange?.(updated);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('samatu:project-recompute', {
        detail: { projectId: project.id, reason: `outline-${op.kind}`, roomNr: op.nr ?? op.keptNr, quiet: true },
      }));
    }
    return { undo: makeOutlineUndo(undoable || {}) };
  };

  // A door or window changed on the drawing (Pathon v3 W5-A A2 / A9): `update(elementai) → elementai`, saved like
  // the room sheet's opening edit (lib/roomSheet openingsPatch — `_angos_user_at` marks the openings as his) and
  // recomputed on the usual path; „Atšaukti" puts the room's openings back as they were.
  const handleRoomOpenings = async (roomNr, update) => {
    await flushProjectSaves().catch(() => null);
    const fresh = getProject(project.id) || project;
    const before = (fresh.patalpos || []).find((r) => String(r?.nr) === String(roomNr));
    if (!before) throw new Error(`Patalpa ${roomNr} nerasta`);
    const elementai = update(Array.isArray(before.elementai) ? before.elementai : []);
    if (!elementai) return null;
    const restore = { elementai: before.elementai, _angos_user_at: before._angos_user_at };   // undefined = absent again (JSON drops it)
    const recompute = (reason) => {
      if (typeof window === 'undefined') return;
      window.dispatchEvent(new CustomEvent('samatu:project-recompute', { detail: { projectId: project.id, reason, roomNr, quiet: true } }));
    };
    const ticket = ticketFor(undoRegistryRef.current, [String(roomNr)]);
    const updated = updateProject(project.id, roomPatchFields(fresh, { [String(roomNr)]: { elementai, _angos_user_at: new Date().toISOString() } }));
    if (updated) onProjectChange?.(updated);
    recompute('openings-edited');
    return {
      undo: () => {
        if (!isNewest(undoRegistryRef.current, ticket)) { toast.info(UNDO_SUPERSEDED); return; }
        ticketFor(undoRegistryRef.current, [String(roomNr)]);
        const now = getProject(project.id) || project;
        const back = updateProject(project.id, roomPatchFields(now, { [String(roomNr)]: restore }));
        if (back) onProjectChange?.(back);
        recompute('openings-undone');
        toast.success(`Atšaukta: patalpos ${roomNr} angos grąžintos`, { description: 'Kiekiai perskaičiuojami.' });
      },
    };
  };

  // Persist measurements + per-page calibration scales from the viewer's local
  // state onto the project. New top-level keys (measurements / pageScalesDurable)
  // ride the existing project JSON — zero backend changes. The viewer debounces.
  // FIELD-SCOPED patch (P0-2, arch review 2026-07-12): updateProject merges
  // onto the CURRENT stored project, so a render-captured `project` spread can
  // no longer revert concurrent writes (async polygon patches, panel price
  // edits, a second tab) that landed after this component last rendered.
  // v3 W5-D D12: a sheet whose only zone is a legend is typed „Legenda" when the reading gave it no type
  const pagesRead = project?.puslapiai || project?.v8_pages;
  const zonesRead = project?._meta?.zonos;
  const sheetPages = useMemo(() => withZoneSheetTypes(pagesRead || [], zonesRead), [pagesRead, zonesRead]);

  const handleMeasureDataChange = ({ measurements, measureScales, countTypes }) => {
    // v3 M7: a sheet crossing the measured limit gets one plain warning (never blocked).
    for (const hit of sheetsCrossingLimit(project?.measurements, measurements)) {
      toast.warning(sheetLimitMessage(hit), { id: `measure-limit-${hit.page}`, duration: 12000 });
    }
    // v3 W2-B: a count made from a legend row keeps its sąmata row in step with the marks (no „Į sąmatą" click)
    const rows = getProject(project.id)?.darbu_sarasas || project.darbu_sarasas || [];
    const synced = syncLegendRows(rows, measurements, countTypes || project.countTypes || []);
    const updated = updateProject(project.id, {
      measurements,
      pageScalesDurable: measureScales,
      ...(countTypes ? { countTypes } : {}),
      ...(synced !== rows ? { darbu_sarasas: synced } : {}),
      // v3 W5-D: the legend counts by kind (backend fixture_rows_flag contract) follow the marks
      _legendos_kiekiai: legendCounts({ measurements, countTypes: countTypes || project.countTypes || [] }),
    });
    if (updated) onProjectChange?.(updated);
  };

  // Sheet names / types / groups the user set in the viewer's sheet rail (Togal-v2 W7) — a frontend
  // key on the project blob like `measurements`. The links between sheets are read server side from
  // the SAVED blob, so they are asked for again (version bump) once this save has landed.
  const [sheetLinksVersion, setSheetLinksVersion] = useState(0);
  const handleSheetOverridesChange = (next) => {
    const updated = updateProject(project.id, { sheet_overrides: next });
    if (updated) onProjectChange?.(updated);
    flushProjectSaves().finally(() => setSheetLinksVersion((v) => v + 1));
  };

  // Per-room canvas visibility handlers (panel eye toggles, Phase 1 declutter).
  const handleToggleRoomVisibility = (nr) => {
    const key = String(nr);
    setHiddenRoomNrs((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Ctrl/Cmd+click isolate: hide every OTHER room; a second isolate on the
  // already-isolated room restores all.
  const handleIsolateRoom = (nr) => {
    const key = String(nr);
    const allNrs = (project.v8_rooms || project.patalpos || []).map((r) => String(r.nr));
    const others = allNrs.filter((n) => n !== key);
    setHiddenRoomNrs((prev) => {
      const alreadyIsolated = !prev.has(key)
        && others.length > 0
        && others.every((n) => prev.has(n));
      return alreadyIsolated ? new Set() : new Set(others);
    });
  };

  // Quantities Panel: hide or show a whole line's rooms at once, and „show only these rooms".
  const handleSetRoomsHidden = (nrs, hidden) => {
    setHiddenRoomNrs((prev) => {
      const next = new Set(prev);
      nrs.forEach((nr) => (hidden ? next.add(String(nr)) : next.delete(String(nr))));
      return next;
    });
  };
  const handleIsolateRooms = (nrs) => {
    const keep = new Set(nrs.map(String));
    const allNrs = (project.v8_rooms || project.patalpos || []).map((r) => String(r.nr));
    setHiddenRoomNrs(new Set(allNrs.filter((n) => !keep.has(n))));
  };

  const [embedEngine] = useState(viewerEngineIsEmbed);

  const pageMetaDict = useMemo(() => buildPageMetaDict(project),
    [project.puslapiai, project.v8_pages]);
  const missingTypes = useMemo(() => missingInteriorTypes(project.puslapiai),
    [project.puslapiai]);

  // Sprint §12 (2026-04-29): mobile responsive — stack vertically on <md.
  // Detect viewport width once on mount; resizer hidden on mobile so user
  // doesn't see a non-functional element.
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches
  );
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(max-width: 767px)');
    const handler = (e) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // The scales the dimension-string lane read off each plan sheet („1:50")
  // — exact, shown in the status bar instead of „nekalibruotas", with where
  // each comes from: written on the sheet or measured from the dimensions.
  const laneScales = useMemo(() => laneScalesOf(project), [project]);

  // Legacy viewer (?viewer=legacy) symbol counting → a sąmata line. Moved out of the JSX unchanged.
  const handleSymbolCountResult = (symbolType, result) => {
    // Pridedam į projekto darbų sąrašą kaip naują eilutę.
    // Naudoja rangovas-kompatibilų pozicijos pavadinimą + kategoriją.
    const aprasymas = SYMBOL_LABELS[symbolType]
      ? t(`project.interiorWorkspace.symbols.${symbolType}`)
      : t('project.interiorWorkspace.symbolCountFallback', { type: symbolType });
    const skyrius = SYMBOL_CATEGORIES[symbolType]
      ? t(`project.interiorWorkspace.categories.${symbolType}`)
      : t('project.interiorWorkspace.otherWorks');
    const kiekis = result?.count || (result?.matches?.length ?? 0);
    if (!kiekis) return;
    // Fresh read + field-scoped write: the counting round-trip is
    // async, and the old `{...project, darbu_sarasas}` blob write
    // also skipped onProjectChange — so React kept the pre-count
    // list and the next edit wiped the new line. (2026-07-27 audit.)
    const fresh = getProject(project.id) || project;
    const darbai = [...(fresh.darbu_sarasas || [])];
    const maxNr = darbai.reduce((m, d) => Math.max(m, d.eil_nr || 0), 0);
    // Tikrinam ar tokia eilutė jau egzistuoja — jei taip, atnaujiname kiekį
    const existingIdx = darbai.findIndex(d =>
      (d.aprasymas || '').toLowerCase() === aprasymas.toLowerCase());
    if (existingIdx >= 0) {
      darbai[existingIdx] = {
        ...darbai[existingIdx],
        kiekis,
        detected: true,
        source: 'Pažymėjus brėžinyje',
        confidence: 'medium',
      };
    } else {
      darbai.push({
        eil_nr: maxNr + 1,
        skyrius,
        aprasymas,
        mato_vnt: 'vnt',
        kiekis,
        kaina: 0,
        suma: 0,
        detected: true,
        source: 'Pažymėjus brėžinyje',
        confidence: 'medium',
      });
    }
    const updated = updateProject(project.id, { darbu_sarasas: darbai });
    if (updated) onProjectChange?.(updated);
  };

  // „Įkelti brėžinį" when the stored PDF is gone. Moved out of the JSX unchanged.
  const handleAttachPdf = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setAttachingPdf(true);
    try {
      // Local cache first — has_pdf is only set once this
      // succeeded, so the flag can never claim a drawing the
      // browser doesn't have.
      await savePdf(project.id, file);
      const [u, b] = await Promise.all([getPdfUrl(project.id), getPdfBlob(project.id)]);
      setPdfUrl(u);
      setPdfBlob(b);
      setPdfMissing(!u);
      // Field-scoped (same class as the writes above): the await
      // above means `project` is a pre-upload snapshot.
      const updated = updateProject(project.id, {
        pdf_name: file.name, has_pdf: true,
      });
      if (updated) onProjectChange?.(updated);
      // …then the DURABLE copy (2026-07-28 audit). Re-attach used
      // to write IndexedDB only, so the re-attached drawing was
      // lost again on the next cache clear / device switch —
      // unlike NewProject, which has always uploaded. Same
      // fire-and-forget idiom as NewProject.jsx.
      uploadPdfToBackend(project.id, file).then((ok) => {
        if (!ok) {
          console.warn('[InteriorWorkspace] backend PDF upload failed');
          toast.warning(t('project.interiorWorkspace.pdfBackupFailed'));
        }
      }).catch((e) => console.warn('[InteriorWorkspace] upload error:', e));
    } catch (e) {
      // No catch at all before this: the rejection surfaced as an
      // unhandled promise, the spinner cleared, and nothing told
      // the user their drawing had NOT been attached.
      console.error('[InteriorWorkspace] PDF attach failed:', e);
      toast.error(t('project.interiorWorkspace.pdfAttachFailed'));
    } finally {
      setAttachingPdf(false);
      event.target.value = '';
    }
  };

  // ── Frame geometry ───────────────────────────────────────────────────────────────────────────
  const canvasMode = canvasModeForView(view, { expanded: samataExpanded, noDrawing: pdfMissing });
  const strip = canvasMode === 'strip';
  const rootRef = useRef(null);
  const canvasColRef = useRef(null);
  const [workspaceWidth, setWorkspaceWidth] = useState(0);
  // The drawing's last real width: behind the strip the viewer keeps it, so collapsing and expanding never
  // re-fits the sheet or loses his zoom.
  const [canvasWidth, setCanvasWidth] = useState(0);
  useEffect(() => {
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(() => {
      if (rootRef.current) setWorkspaceWidth(Math.round(rootRef.current.getBoundingClientRect().width));
      const col = canvasColRef.current;
      if (col && !col.dataset.strip) {
        const w = Math.round(col.getBoundingClientRect().width);
        if (w > STRIP_WIDTH * 2) setCanvasWidth(w);
      }
    });
    if (rootRef.current) ro.observe(rootRef.current);
    if (canvasColRef.current) ro.observe(canvasColRef.current);
    return () => ro.disconnect();
  }, []);
  // The panel's width, as he dragged it: one for the drawing view (300–480 px, `samatu_panel_width`), one
  // for the wide Patikra / Sąmata panel. Remembered per browser when a drag ends.
  const [storedWidths, setStoredWidths] = useState(() => ({
    full: typeof window !== 'undefined' ? readPanelWidth(window.localStorage, 'full') : null,
    split: typeof window !== 'undefined' ? readPanelWidth(window.localStorage, 'split') : null,
  }));
  const panelWidth = panelWidthFor(canvasMode, {
    workspaceWidth,
    stored: canvasMode === 'split' ? storedWidths.split : storedWidths.full,
  });
  const widthMode = canvasMode === 'split' ? 'split' : 'full';
  const panelMin = PANEL_LIMITS[widthMode].min;
  const panelMax = widthMode === 'split' && workspaceWidth > 0
    ? Math.max(panelMin, Math.min(PANEL_LIMITS.split.max, workspaceWidth - MIN_SPLIT_CANVAS))
    : PANEL_LIMITS[widthMode].max;
  const handlePanelWidth = useCallback((width, { final } = {}) => {
    setStoredWidths((prev) => ({ ...prev, [widthMode]: width }));
    if (final && typeof window !== 'undefined') writePanelWidth(window.localStorage, widthMode, width);
  }, [widthMode]);
  const hiddenViewerWidth = canvasWidth || Math.max(480, (workspaceWidth || 1200) - (panelWidthFor('full', { workspaceWidth }) || 340));

  // What the panel's contents get from the frame (components/project/workspaceHost): its width, a way to
  // hand Patikra's saved project back to the top bar, the two-way highlight hooks, and the drawing itself
  // for a check view.
  const patikraProjectRef = useRef(onPatikraProject);
  patikraProjectRef.current = onPatikraProject;
  const hostProjectChange = useCallback((next) => patikraProjectRef.current?.(next), []);
  // „Show me this place" — a fact's evidence, a room's frame: the drawing jumps there and fits it.
  const revealNonce = useRef(0);
  const [revealFocus, setRevealFocus] = useState(null);
  const onRevealEvidence = useCallback((where) => {
    const target = revealTarget(where || {}, revealNonce.current + 1);
    if (!target) return;
    revealNonce.current = target.nonce;
    setRevealFocus(target);
  }, []);
  const roomsRef = useRef([]);
  roomsRef.current = project.v8_rooms || project.patalpos || [];
  const onFocusRoom = useCallback((nr) => {
    const room = roomsRef.current.find((r) => String(r?.nr) === String(nr));
    if (!room) return;
    const page = room.puslapio_nr ?? room.page_nr ?? null;
    if (page) setLocalFocusedPage(page);
    setLocalFocusedRoom(room);
  }, []);
  // The drawing lent to Patikra (RoomDrawingPane): what was READ about one room is drawn instead of the
  // room zones, and while he points at the drawing his clicks go to the question, not to the tools.
  const [canvasSlot, setCanvasSlot] = useState(null);
  const [hostedCheck, setHostedCheck] = useState(null);      // {check, pickActive} | null
  const hostedPointRef = useRef(null);
  const hostedPoint = useCallback((pt) => hostedPointRef.current?.(pt), []);
  const canvasReady = Boolean(pdfUrl && embedEngine && !strip && !isMobile);
  const hostValue = useMemo(() => ({
    panelWidth: panelWidth ?? workspaceWidth,
    onProjectChange: hostProjectChange,
    onRevealEvidence,
    onFocusRoom,
    canvasReady,
    canvasSlot,
    setCanvasCheck: setHostedCheck,
    pointRef: hostedPointRef,
  }), [panelWidth, workspaceWidth, hostProjectChange, onRevealEvidence, onFocusRoom, canvasReady, canvasSlot]);
  const viewerCheck = view === 'patikra' ? (hostedCheck?.check || null) : null;
  const picking = Boolean(viewerCheck && hostedCheck?.pickActive);

  const panelLabel = (id) => PANEL_TABS.find((tab) => tab.id === id)?.label || id;

  const viewerNode = pdfUrl ? (
    embedEngine ? (
      <TakeoffViewer
        fileUrl={pdfUrl}
        active={!strip}
        // Patikra's check view on this same viewer (RoomDrawingPane hosted), and „show me this place"
        check={viewerCheck}
        focus={revealFocus}
        onPagePoint={picking ? hostedPoint : null}
        rooms={project?.v8_rooms || project?.patalpos || []}
        focusedRoom={effectiveFocusedRoom}
        focusedPage={effectiveFocusedPage}
        hiddenRoomNrs={hiddenRoomNrs}
        hoveredRoomNrExternal={hoveredRoomNr}
        projectId={project.id}
        pdfBlob={pdfBlob}
        renderToolbarAddon={(page, total) => (
          <>
            <DetectRunButton project={project} currentPage={page} totalPages={total} busy={detectRun.busy} onStart={detectRun.start} />
            <RevisionCompareControl project={project} currentPage={page} overlay={revisionOverlay} onOverlayChange={setRevisionOverlay} onProjectSaved={onProjectChange} />
          </>
        )}
        revisionOverlay={revisionOverlay}
        onClearFocus={() => { setLocalFocusedRoom(null); setLocalFocusedPage(null); }}
        onRoomPolygonFill={handleRoomPolygonFill}
        onRoomOutlineEdit={handleRoomOutlineEdit}
        onOutlineTool={handleOutlineTool}
        onRoomToolPreview={handleRoomToolPreview}
        onRoomToolCommit={handleRoomToolCommit}
        onRoomOpenings={handleRoomOpenings}
        fillRequest={fillRequest}
        exportFileName={`${(project?.name || 'brezinys').trim().replace(/[\\/:*?"<>|]+/g, '-')}.pdf`}
        initialMeasurements={project?.measurements || []}
        initialMeasureScales={project?.pageScalesDurable || {}}
        laneScales={laneScales}
        project={project}
        initialCountTypes={project?.countTypes || null}
        onMeasureDataChange={handleMeasureDataChange}
        legendPanelSlot={legendSlot}
        onLegendPanelChange={setLegendOpen}
        sheetPages={sheetPages}
        sheetOverrides={project?.sheet_overrides || null}
        onSheetOverridesChange={handleSheetOverridesChange}
        sheetLinksVersion={sheetLinksVersion}
        onRoomZoneClick={(room) => {
          if (room?.puslapio_nr) setLocalFocusedPage(room.puslapio_nr);
          setLocalFocusedRoom(room);
          onJumpToPage?.(room.puslapio_nr, room);
        }}
      />
    ) : (
      <PlanViewer
        fileUrl={pdfUrl}
        pageMeta={pageMetaDict}
        missingTypes={missingTypes}
        focusedPage={effectiveFocusedPage}
        focusedRoom={effectiveFocusedRoom}
        rooms={project?.v8_rooms || project?.patalpos || []}
        onRoomZoneClick={(room) => {
          // Canvas → panel: selecting a zone focuses that room. We already
          // are on its page (zones are page-filtered), so puslapio_nr is the
          // current page. effectiveFocusedRoom re-derives the full room from
          // the live patalpos by nr, so {nr, puslapio_nr} is enough to drive
          // both the canvas marker and the panel highlight.
          if (room?.puslapio_nr) setLocalFocusedPage(room.puslapio_nr);
          setLocalFocusedRoom(room);
          onJumpToPage?.(room.puslapio_nr, room);
        }}
        eksplikacija_source_page={project?._eksplikacija?.eksplikacija_source_page}
        pdfFile={pdfBlob}
        onRoomPolygonFill={handleRoomPolygonFill}
        onSymbolCountResult={handleSymbolCountResult}
      />
    )
  ) : pdfMissing ? (
    <div className="flex-1 h-full flex flex-col items-center justify-center p-8 text-center">
      <Layers className="w-12 h-12 text-muted-foreground/40 mb-3" />
      <p className="text-sm text-foreground font-medium mb-1">{t('project.interiorWorkspace.pdfUnavailable')}</p>
      <p className="text-xs text-muted-foreground max-w-sm">
        {t('project.interiorWorkspace.pdfUnavailableDesc')}
      </p>
      <label
        className="mt-4 inline-flex items-center gap-2 px-3 py-2 rounded border border-border bg-card hover:bg-muted/50 cursor-pointer text-sm text-foreground transition-colors"
      >
        <Upload className="w-4 h-4" />
        {attachingPdf ? t('project.interiorWorkspace.attaching') : t('project.interiorWorkspace.attachPdf')}
        <input
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          disabled={attachingPdf}
          onChange={handleAttachPdf}
        />
      </label>
    </div>
  ) : (
    <div className="flex-1 h-full flex items-center justify-center text-muted-foreground text-sm">
      {t('project.interiorWorkspace.loadingDrawing')}
    </div>
  );

  const drawingPanels = {
    patalpos: (
      <WorkspacePanel
        project={project}
        mode="brezinys"
        onOpenAssumptions={onOpenAssumptions}
        lastRipple={lastRipple}
        focusedRoomNr={effectiveFocusedRoom?.nr ?? null}
        hiddenRoomNrs={hiddenRoomNrs}
        onToggleRoomVisibility={handleToggleRoomVisibility}
        onIsolateRoom={handleIsolateRoom}
        onShowAllRooms={() => setHiddenRoomNrs(new Set())}
        onEditRoomZone={handleEditRoomZone}
        onRoomRowHover={setHoveredRoomNr}
        onJumpToPage={(pageNr, room) => {
          setLocalFocusedPage(pageNr);
          setLocalFocusedRoom(room || null);
          onJumpToPage?.(pageNr, room);
        }}
        onJumpToProvenance={(room) => {
          // Eksplikacija chips open an in-place data popover (handled inside
          // WorkspacePanel). Other sources (manual_polygon, vision, dimension)
          // jump to the room's page so the user can find it visually.
          const src = room.plotas_source;
          if (src === 'manual_polygon') {
            const targetPage = room.page_nr ?? room.puslapio_nr;
            if (targetPage && onJumpToPage) onJumpToPage(targetPage, room);
          } else if (src && src !== 'eksplikacija') {
            const targetPage = room.puslapio_nr ?? room.page_nr;
            if (targetPage && onJumpToPage) onJumpToPage(targetPage, room);
          }
        }}
        onProjectChange={onProjectChange}
      />
    ),
    kiekiai: (
      <QuantitiesPanel
        project={project}
        rooms={project.v8_rooms || project.patalpos || []}
        focusedRoomNr={effectiveFocusedRoom?.nr ?? null}
        hiddenRoomNrs={hiddenRoomNrs}
        onFocusRoom={(room) => {
          setLocalFocusedPage(room.puslapio_nr ?? null);
          setLocalFocusedRoom(room);
          onJumpToPage?.(room.puslapio_nr, room);
        }}
        onToggleRoomVisibility={handleToggleRoomVisibility}
        onSetRoomsHidden={handleSetRoomsHidden}
        onIsolateRooms={handleIsolateRooms}
        onRoomRowHover={setHoveredRoomNr}
        onOpenAssumptions={onOpenAssumptions ? () => onOpenAssumptions() : null}
        onActiveRowChange={setKiekiaiActiveRow}
        onAddToChat={(what) => {
          setChatAddRequest({ ...what, nonce: Date.now() });
          setRightTab('pokalbis');
        }}
        onProjectChange={onProjectChange}
        onJumpToPage={(pageNr) => { setLocalFocusedPage(pageNr); onJumpToPage?.(pageNr); }}
      />
    ),
    pokalbis: (
      <AiChat
        project={project}
        focusedRoomNr={effectiveFocusedRoom?.nr ?? null}
        activeRow={kiekiaiActiveRow}
        addRequest={chatAddRequest}
      />
    ),
  };

  const panels = [
    { id: 'patalpos', keepMounted: true, node: drawingPanels.patalpos },
    { id: 'kiekiai', keepMounted: true, node: drawingPanels.kiekiai },
    {
      id: 'patikra',
      scroll: true,
      node: view === 'patikra' ? (
        <WorkspaceHostContext.Provider value={hostValue}>
          <Suspense fallback={<p className="p-4 text-[14px] text-muted-foreground">{t('project.roomSheet.loading')}</p>}>
            <PatikraEntry />
          </Suspense>
        </WorkspaceHostContext.Provider>
      ) : null,
    },
    { id: 'samata', scroll: true, node: samataContent ? <div className="px-3 pb-3">{samataContent}</div> : null },
    { id: 'pokalbis', keepMounted: true, node: drawingPanels.pokalbis },
  ];

  // Sąmata: „Išskleisti" gives the rows the whole width (the drawing waits behind a 56 px strip);
  // „Rodyti brėžinį" brings it back beside them. Nothing to bring back without a drawing.
  const samataToggle = view === 'samata' && !pdfMissing ? (
    <button
      type="button"
      data-testid="samata-expand"
      aria-pressed={samataExpanded}
      onClick={() => onSamataExpandedChange?.(!samataExpanded)}
      title={samataExpanded
        ? 'Rodyti brėžinį šalia sąmatos eilučių'
        : 'Išskleisti sąmatą per visą plotį — brėžinys susitrauks į juostą kairėje'}
      className="inline-flex items-center gap-1.5 min-h-[32px] px-2.5 rounded-[2px] border border-border-strong bg-card text-[14px] text-foreground/85 hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {samataExpanded
        ? <><Minimize2 className="w-4 h-4" aria-hidden /> Rodyti brėžinį</>
        : <><Maximize2 className="w-4 h-4" aria-hidden /> Išskleisti</>}
    </button>
  ) : null;

  return (
    <div
      ref={rootRef}
      data-testid="workspace"
      data-view={view}
      data-canvas-mode={canvasMode}
      className={`relative flex flex-col md:flex-row min-h-0 overflow-hidden border-t border-border bg-background ${className}`}
    >
      {/* Phase C-1 Task 24: coarse-pointer (touch) view-only notice. It lived in
          the Konva PdfViewer, which was deleted (dc9a230) — the component
          survived with zero imports, so touch users got no warning at all.
          Mounted on the workspace (the surface it warns about); it pins itself
          to the viewport bottom and self-hides on a mouse pointer / after
          dismissal. (Re-mounted 2026-07-28 UX walkthrough.) */}
      <MobileViewOnlyBanner />

      {/* THE DRAWING — one column, mounted once. `viewer-root` keeps its identity across every view. */}
      <div
        ref={canvasColRef}
        data-testid="viewer-root"
        data-strip={strip ? '1' : undefined}
        className={`relative flex flex-col min-w-0 min-h-0 border-b md:border-b-0 md:border-r border-border ${strip ? 'shrink-0' : 'flex-1'}`}
        style={strip
          ? (isMobile ? { height: STRIP_WIDTH } : { width: STRIP_WIDTH })
          : (isMobile ? { height: '60%' } : undefined)}
      >
        {/* the run pill — bottom centre, above the mode pill's row, clear of the top row of tool cards (C5) */}
        {detectRun.run && !strip && (
          <div className="pointer-events-none absolute inset-x-0 bottom-14 z-30 flex justify-center px-4">
            <DetectRunProgress run={detectRun.run} view={detectRun.view} groups={project?._meta?.geometrija?.grupes} onDismiss={detectRun.dismiss} onRetry={detectRun.retry} />
          </div>
        )}
        {detecting && !strip && (
          <div className="shrink-0 flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 border-b border-blue-500/30 text-xs text-blue-300">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
            {t('project.interiorWorkspace.detecting')}
          </div>
        )}
        {/* Patikra's drawing controls („Į patalpą", „Visas lapas", what to click, the wall legend) — right
            above the drawing they act on (RoomDrawingPane portals here); empty and hidden otherwise. */}
        <div
          ref={setCanvasSlot}
          data-testid="canvas-slot"
          className="shrink-0 max-h-[45%] overflow-y-auto border-b border-border bg-card px-3 py-2 empty:hidden"
        />
        <div
          className={`relative flex-1 min-h-0 overflow-hidden ${picking ? 'ring-2 ring-inset ring-[hsl(var(--accent-2))] [&_*]:!cursor-crosshair' : ''}`}
          data-picking={picking ? '1' : undefined}
        >
          <div
            aria-hidden={strip || undefined}
            className="h-full flex flex-col"
            style={strip
              ? { position: 'absolute', top: 0, bottom: 0, left: 0, width: hiddenViewerWidth, visibility: 'hidden', pointerEvents: 'none' }
              : undefined}
          >
            {viewerNode}
          </div>
          {strip && (
            <button
              type="button"
              data-testid="canvas-strip"
              onClick={() => (view === 'samata' && !pdfMissing ? onSamataExpandedChange?.(false) : onViewChange?.('brezinys'))}
              title={view === 'samata' && !pdfMissing ? 'Rodyti brėžinį šalia sąmatos' : 'Grįžti į brėžinį'}
              aria-label={view === 'samata' && !pdfMissing ? 'Rodyti brėžinį šalia sąmatos' : 'Grįžti į brėžinį'}
              className="absolute inset-0 flex md:flex-col items-center justify-center gap-2 bg-card hover:bg-muted/60 text-foreground/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
            >
              <MapIcon className="w-5 h-5 shrink-0" aria-hidden />
              <span className="text-[14px] font-medium md:[writing-mode:vertical-rl]">Brėžinys</span>
            </button>
          )}
        </div>
      </div>

      {/* THE RIGHT PANEL — a mode host; on Siųsti the screen itself takes its place. */}
      {view === 'siusti' ? (
        <div data-testid="send-view" className="flex-1 min-w-0 min-h-0 overflow-y-auto p-4 space-y-3">
          {notices}
          {sendContent}
        </div>
      ) : (
        <RightPanelHost
          tabs={PANEL_TABS.map((tab) => ({ ...tab, label: panelLabel(tab.id) }))}
          activeTab={rightTab}
          onTabChange={setRightTab}
          width={isMobile ? null : panelWidth}
          grow={strip || isMobile}
          minWidth={panelMin}
          maxWidth={panelMax}
          onWidthChange={isMobile || strip ? null : handlePanelWidth}
          notices={notices}
          tabBarExtra={samataToggle}
          panels={panels}
          cover={legendOpen && !strip ? <div ref={setLegendSlot} className="h-full min-h-0" data-testid="legend-panel-slot" /> : null}
        />
      )}
    </div>
  );
}
