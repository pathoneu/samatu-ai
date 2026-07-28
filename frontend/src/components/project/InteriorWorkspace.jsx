/**
 * InteriorWorkspace — auto-count stiliaus split-screen interjero takeoff workflow.
 *
 * Layout:
 *   ┌───────────────────────────────────────────────────────┐
 *   │ Header: projektas, mastelio statusas, AI/Industries    │
 *   ├──────────────────────────┬────────────────────────────┤
 *   │                          │  TOTALS PANEL (sticky top) │
 *   │                          │  - Dažomas plotas          │
 *   │   PDF + POLYGON CANVAS   │  - Kampai                  │
 *   │       (60% width)        │  - Lubos                   │
 *   │                          ├────────────────────────────┤
 *   │                          │  PATALPŲ SĄRAŠAS          │
 *   │                          │  (RoomsGrid scroll'a)      │
 *   │                          │                            │
 *   │                          ├────────────────────────────┤
 *   │                          │  DARBŲ SĄRAŠAS             │
 *   └──────────────────────────┴────────────────────────────┘
 *
 * Vartotojas mato VISKĄ vienu metu — brūkšnioja polygon'ą kairėje,
 * mato totals atsinaujinant dešinėje real-time.
 */

import { useState, useMemo, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Layers, Upload } from 'lucide-react';
import PlanViewer from './PlanViewer';
import TakeoffViewer from '@/components/viewer/TakeoffViewer';
import WorkspacePanel from './WorkspacePanel';
import OnboardingTooltips from './OnboardingTooltips';
import MobileViewOnlyBanner from './MobileViewOnlyBanner';
import { toast } from 'sonner';
import { getPdfUrl, getPdfBlob, savePdf, uploadPdfToBackend } from '@/lib/pdfStore';
import { getProject, updateProject } from '@/lib/projectStore';
import { buildPageMetaDict, missingInteriorTypes } from '@/lib/pageTypes';
import { detectRoomPolygons } from '@/lib/detectRoomPolygonsApi';

const DETECTED_SOURCES = ['auto_floodfill', 'corrected', 'manual', 'manual_needed'];

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
  focusedPage = null,
  focusedRoom = null,
  onJumpToPage = null,
  onProjectChange = null,
}) {
  const { t } = useTranslation();
  const [pdfUrl, setPdfUrl] = useState(null);
  const [pdfBlob, setPdfBlob] = useState(null);  // Diena 6: V9 click-to-count'ui
  // Sprint H7 (2026-04-29): default 70/30 — PDF gets more central space.
  // Resizer still allows 40-75 range so user can adjust if their panel is dense.
  const [splitRatio, setSplitRatio] = useState(70);
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
  const effectiveFocusedPage = localFocusedPage ?? focusedPage;
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
    // (Phase A: Beržų auto >= 8, wrong_room_fills = 0 on every project). The
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
    const updated = updateProject(project.id, roomPatchFields(fresh, { [String(roomNr)]: patch }));
    if (updated) onProjectChange?.(updated);
  };

  // Persist measurements + per-page calibration scales from the viewer's local
  // state onto the project. New top-level keys (measurements / pageScalesDurable)
  // ride the existing project JSON — zero backend changes. The viewer debounces.
  // FIELD-SCOPED patch (P0-2, arch review 2026-07-12): updateProject merges
  // onto the CURRENT stored project, so a render-captured `project` spread can
  // no longer revert concurrent writes (async polygon patches, panel price
  // edits, a second tab) that landed after this component last rendered.
  const handleMeasureDataChange = ({ measurements, measureScales, countTypes }) => {
    const updated = updateProject(project.id, {
      measurements,
      pageScalesDurable: measureScales,
      ...(countTypes ? { countTypes } : {}),
    });
    if (updated) onProjectChange?.(updated);
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

  return (
    <div className="flex flex-col md:flex-row h-[calc(100vh-180px)] min-h-[600px] border border-border rounded-lg overflow-hidden bg-background relative">
      {/* Sprint H8: 3-step onboarding overlay (auto-skips after first time) */}
      <OnboardingTooltips />
      {/* Phase C-1 Task 24: coarse-pointer (touch) view-only notice. It lived in
          the Konva PdfViewer, which was deleted (dc9a230) — the component
          survived with zero imports, so touch users got no warning at all.
          Mounted on the workspace (the surface it warns about); it pins itself
          to the viewport bottom and self-hides on a mouse pointer / after
          dismissal. (Re-mounted 2026-07-28 UX walkthrough.) */}
      <MobileViewOnlyBanner />
      {/* LEFT (md+) / TOP (mobile): PDF + AI overlay (auto-count-style) */}
      <div
        className="flex flex-col border-b md:border-b-0 md:border-r border-border w-full md:w-auto"
        style={{ width: isMobile ? '100%' : `${splitRatio}%`, height: isMobile ? '60%' : 'auto' }}
      >
        {detecting && (
          <div className="shrink-0 flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 border-b border-blue-500/30 text-xs text-blue-300">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
            {t('project.interiorWorkspace.detecting')}
          </div>
        )}
        {pdfUrl ? (
          viewerEngineIsEmbed() ? (
            <TakeoffViewer
              fileUrl={pdfUrl}
              rooms={project?.v8_rooms || project?.patalpos || []}
              focusedRoom={effectiveFocusedRoom}
              focusedPage={effectiveFocusedPage}
              hiddenRoomNrs={hiddenRoomNrs}
              hoveredRoomNrExternal={hoveredRoomNr}
              projectId={project.id}
              pdfBlob={pdfBlob}
              onClearFocus={() => { setLocalFocusedRoom(null); setLocalFocusedPage(null); }}
              onRoomPolygonFill={handleRoomPolygonFill}
              fillRequest={fillRequest}
              exportFileName={`${(project?.name || 'brezinys').trim().replace(/[\\/:*?"<>|]+/g, '-')}.pdf`}
              initialMeasurements={project?.measurements || []}
              initialMeasureScales={project?.pageScalesDurable || {}}
              initialCountTypes={project?.countTypes || null}
              onMeasureDataChange={handleMeasureDataChange}
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
              // current page. effectiveFocusedRoom (line ~114) re-derives the
              // full room from the live patalpos by nr, so {nr, puslapio_nr} is
              // enough to drive both the canvas marker and the panel highlight.
              if (room?.puslapio_nr) setLocalFocusedPage(room.puslapio_nr);
              setLocalFocusedRoom(room);
              onJumpToPage?.(room.puslapio_nr, room);
            }}
            eksplikacija_source_page={project?._eksplikacija?.eksplikacija_source_page}
            pdfFile={pdfBlob}
            onRoomPolygonFill={handleRoomPolygonFill}
            onSymbolCountResult={(symbolType, result) => {
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
            }}
          />
          )
        ) : pdfMissing ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
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
                onChange={async (event) => {
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
                }}
              />
            </label>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
            {t('project.interiorWorkspace.loadingDrawing')}
          </div>
        )}
      </div>

      {/* Resizer — only on desktop. Mobile uses fixed 60/40 vertical split. */}
      {!isMobile && (
        <div
          className="w-1 hover:bg-foreground/20 cursor-col-resize transition-colors shrink-0"
          onMouseDown={(e) => {
            const startX = e.clientX;
            const startRatio = splitRatio;
            const containerWidth = e.currentTarget.parentElement.offsetWidth;
            const onMove = (ev) => {
              const delta = ((ev.clientX - startX) / containerWidth) * 100;
              setSplitRatio(Math.max(40, Math.min(75, startRatio + delta)));
            };
            const onUp = () => {
              window.removeEventListener('mousemove', onMove);
              window.removeEventListener('mouseup', onUp);
            };
            window.addEventListener('mousemove', onMove);
            window.addEventListener('mouseup', onUp);
          }}
        />
      )}

      {/* RIGHT (md+) / BOTTOM (mobile): Kompaktinė sąmatos panelė */}
      <div
        style={{ width: isMobile ? '100%' : `${100 - splitRatio}%`, height: isMobile ? '40%' : 'auto' }}
        className="overflow-hidden"
      >
        <WorkspacePanel
          project={project}
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
      </div>
    </div>
  );
}
