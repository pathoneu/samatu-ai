/**
 * ProjectCanvas — Togal-style single-canvas layout (Etap 2).
 *
 * Layout:
 *   ┌─ HEADER (32px) ──────────────────────────────────────┐
 *   │ ← Pavadinimas             [⚙] [💾 Eksportuoti ▾]  │
 *   ├─────────┬──────────────────────┬───────────────────┤
 *   │ SHEETS  │  PDF + AI overlay    │ POZICIJŲ PANELĖ   │
 *   │ (60px)  │  (auto)              │ (resizable)        │
 *   │         │                      │                    │
 *   └─────────┴──────────────────────┴───────────────────┘
 *
 * State:
 *   - panelWidth (localStorage 'samatu_panel_width', default 380)
 *   - panelCollapsed (lokalus state, NOT persisted)
 *   - activeRowId (which darbu_sarasas eilutė selected)
 *   - hoveredRowId (which row mouse is hovering for pulse)
 *
 * Naudojimas (zamenina InteriorWorkspace + ProjectMainView):
 *   <ProjectCanvas project={project} onProjectChange={...} />
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import PdfViewer from './PdfViewer';
import PositionsPanel from './PositionsPanel';
import { getPdfUrl, getPdfBlob } from '@/lib/pdfStore';
import { updateProject } from '@/lib/projectStore';

const PANEL_MIN = 200;
const PANEL_MAX = 800;
const PANEL_DEFAULT = 380;
const PANEL_KEY = 'samatu_panel_width';

function loadPanelWidth() {
  try {
    const saved = parseInt(localStorage.getItem(PANEL_KEY), 10);
    if (Number.isFinite(saved) && saved >= PANEL_MIN && saved <= PANEL_MAX) {
      return saved;
    }
  } catch {}
  return PANEL_DEFAULT;
}

export default function ProjectCanvas({ project, onProjectChange }) {
  const [pdfUrl, setPdfUrl] = useState(null);
  const [pdfBlob, setPdfBlob] = useState(null);
  const [pdfMissing, setPdfMissing] = useState(false);

  const [panelWidth, setPanelWidth] = useState(loadPanelWidth);
  const [panelCollapsed, setPanelCollapsed] = useState(false);

  // Trace state — bendras tarp PdfCanvas ir PositionsPanel
  const [activeRowId, setActiveRowId] = useState(null);
  const [hoveredRowId, setHoveredRowId] = useState(null);

  // Page state — kuris brėžinio puslapis aktyvus (auto-switch ant linko click'o)
  const [focusedPage, setFocusedPage] = useState(null);

  // PDF blob/URL load
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
      });
    return () => {
      revoked = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [project.id]);

  // Persist panel width
  useEffect(() => {
    try { localStorage.setItem(PANEL_KEY, String(panelWidth)); } catch {}
  }, [panelWidth]);

  // Drag handle
  const handleDragStart = useCallback((e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = panelWidth;
    const onMove = (ev) => {
      const delta = startX - ev.clientX;  // tempiam į kairę → didesnis
      const next = Math.max(PANEL_MIN, Math.min(PANEL_MAX, startW + delta));
      setPanelWidth(next);
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [panelWidth]);

  // pageMeta dict (per puslapio info iš v8_pages)
  const pageMetaDict = useMemo(() => {
    const dict = {};
    (project.v8_pages || []).forEach(p => {
      dict[p.page] = { label: p.label, type: p.type, confidence: p.confidence };
    });
    return dict;
  }, [project.v8_pages]);

  // darbu_sarasas with stable IDs (jei nėra eil_nr)
  const darbai = useMemo(() => {
    return (project.darbu_sarasas || []).map((d, i) => ({
      ...d,
      _id: d.eil_nr ? `nr-${d.eil_nr}` : `idx-${i}`,
    }));
  }, [project.darbu_sarasas]);

  const handleRowClick = useCallback((row) => {
    setActiveRowId(row._id);
    // Auto-jump į puslapį, jei trace_links rodo kitą puslapį
    const links = row.trace_links || [];
    if (links.length > 0) {
      const targetPage = links[0].page_nr;
      if (targetPage && targetPage !== focusedPage) {
        setFocusedPage(targetPage);
      }
    }
  }, [focusedPage]);

  const handleRowHover = useCallback((row) => {
    setHoveredRowId(row?._id || null);
  }, []);

  const handleDarbaiChange = useCallback((newDarbai) => {
    const cleaned = newDarbai.map(({ _id, ...rest }) => rest);
    updateProject(project.id, { ...project, darbu_sarasas: cleaned });
    onProjectChange?.({ ...project, darbu_sarasas: cleaned });
  }, [project, onProjectChange]);

  return (
    <div className="flex h-[calc(100vh-100px)] min-h-[600px] border border-border rounded-lg overflow-hidden bg-background">

      {/* LEFT: PDF + AI overlays */}
      <div className="flex flex-col flex-1 border-r border-border min-w-0">
        {pdfUrl ? (
          <PdfViewer
            fileUrl={pdfUrl}
            projectId={project.id}
            pageMeta={pageMetaDict}
            aiRooms={project.v8_rooms}
            pdfFile={pdfBlob}
            focusedPage={focusedPage}
            activeRowId={activeRowId}
            hoveredRowId={hoveredRowId}
            darbuSarasas={darbai}
            onAiRoomClick={(room) => {
              // TODO Etap 3: atidaryti RoomTooltip su pozicijomis
              console.log('[room-click]', room);
            }}
            onSymbolCountResult={(symbolType, result) => {
              // Pridedam į darbų sąrašą (esama logika iš InteriorWorkspace)
              const SYMBOL_LABELS = {
                rozetes: 'Rozetės/jungiklio komutavimas',
                jungikliai: 'Rozetės/jungiklio komutavimas',
                sviestuvai: 'Lubinių priglaistomų šviestuvų apdirbimas',
                difuzoriai: 'Difūzorių apdirbimas (ventiliacijos taškai)',
                klozetai: 'Klozeto montavimas',
                trapai: 'Linijinio latako montavimas (vonios drenažas)',
                maisytuvai: 'Maišytuvų montavimas',
                gyvatukai: 'Gyvatuko (rankšluosčių džiovintuvo) montavimas',
                durys: 'Durys (vidaus)', langai: 'Langai',
              };
              const SYMBOL_CATEGORIES = {
                rozetes: 'Elektra', jungikliai: 'Elektra',
                sviestuvai: 'Apšvietimas', difuzoriai: 'Ventiliacija',
                klozetai: 'Santechnika', trapai: 'Santechnika',
                maisytuvai: 'Santechnika', gyvatukai: 'Santechnika',
                durys: 'GKP', langai: 'GKP',
              };
              const aprasymas = SYMBOL_LABELS[symbolType] || `Simbolių skaičius (${symbolType})`;
              const skyrius = SYMBOL_CATEGORIES[symbolType] || 'Kiti darbai';
              const kiekis = result?.count || (result?.matches?.length ?? 0);
              if (!kiekis) return;
              const next = [...darbai];
              const idx = next.findIndex(d =>
                (d.aprasymas || '').toLowerCase() === aprasymas.toLowerCase());
              if (idx >= 0) {
                next[idx] = { ...next[idx], kiekis, detected: true,
                              source: 'AI Vision (click-to-count)', confidence: 'medium' };
              } else {
                const maxNr = next.reduce((m, d) => Math.max(m, d.eil_nr || 0), 0);
                next.push({
                  eil_nr: maxNr + 1, skyrius, aprasymas, mato_vnt: 'vnt',
                  kiekis, kaina: 0, suma: 0, detected: true,
                  source: 'AI Vision (click-to-count)', confidence: 'medium',
                  trace_type: 'counted',
                });
              }
              handleDarbaiChange(next);
            }}
          />
        ) : pdfMissing ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <p className="text-sm text-foreground font-medium mb-1">Brėžinys nepasiekiamas</p>
            <p className="text-xs text-muted-foreground max-w-sm">
              Šis projektas sukurtas anksčiau ir PDF nebuvo išsaugotas.
            </p>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
            Krauname brėžinį…
          </div>
        )}
      </div>

      {/* DRAG HANDLE */}
      {!panelCollapsed && (
        <div
          onMouseDown={handleDragStart}
          className="w-1 hover:w-1.5 hover:bg-foreground/20 cursor-col-resize transition-all shrink-0 bg-border"
          title="Tempk keisti panel'ės plotį"
        />
      )}

      {/* RIGHT: Pozicijų panel'ė */}
      {!panelCollapsed ? (
        <div
          className="flex flex-col bg-card border-l border-border shrink-0"
          style={{ width: `${panelWidth}px` }}
        >
          <PositionsPanel
            project={project}
            darbai={darbai}
            activeRowId={activeRowId}
            hoveredRowId={hoveredRowId}
            onRowClick={handleRowClick}
            onRowHover={handleRowHover}
            onDarbaiChange={handleDarbaiChange}
            onCollapse={() => setPanelCollapsed(true)}
          />
        </div>
      ) : (
        <button
          onClick={() => setPanelCollapsed(false)}
          className="w-6 bg-card border-l border-border hover:bg-muted/40 flex items-center justify-center text-muted-foreground hover:text-foreground"
          title="Atidaryti pozicijų panel'ę"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
