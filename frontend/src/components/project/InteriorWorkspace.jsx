/**
 * InteriorWorkspace — Togal-stiliaus split-screen interjero takeoff workflow.
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

import { useState, useMemo, useEffect } from 'react';
import { Layers } from 'lucide-react';
import PdfViewer from './PdfViewer';
import WorkspacePanel from './WorkspacePanel';
import OnboardingTooltips from './OnboardingTooltips';
import { getPdfUrl, getPdfBlob } from '@/lib/pdfStore';
import { updateProject } from '@/lib/projectStore';
import { buildPageMetaDict, missingInteriorTypes } from '@/lib/pageTypes';

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
};

export default function InteriorWorkspace({
  project,
  focusedPage = null,
  focusedRoom = null,
  onJumpToPage = null,
  onProjectChange = null,
}) {
  const [pdfUrl, setPdfUrl] = useState(null);
  const [pdfBlob, setPdfBlob] = useState(null);  // Diena 6: V9 click-to-count'ui
  // Sprint H7 (2026-04-29): default 70/30 — PDF gets more central space.
  // Resizer still allows 40-75 range so user can adjust if their panel is dense.
  const [splitRatio, setSplitRatio] = useState(70);
  const [pdfMissing, setPdfMissing] = useState(false);
  // Local override: when user clicks a room in the right-side panel while
  // already on this view, bump local focused page/room (in addition to
  // bubbling up). Prop changes take priority — local override resets on prop.
  const [localFocusedPage, setLocalFocusedPage] = useState(null);
  const [localFocusedRoom, setLocalFocusedRoom] = useState(null);
  const effectiveFocusedPage = localFocusedPage ?? focusedPage;
  const effectiveFocusedRoom = localFocusedRoom ?? focusedRoom;
  useEffect(() => {
    setLocalFocusedPage(null);
    setLocalFocusedRoom(null);
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
      });
    return () => {
      revoked = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [project.id]);

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
      {/* LEFT (md+) / TOP (mobile): PDF + AI overlay (Togal-style) */}
      <div
        className="flex flex-col border-b md:border-b-0 md:border-r border-border w-full md:w-auto"
        style={{ width: isMobile ? '100%' : `${splitRatio}%`, height: isMobile ? '60%' : 'auto' }}
      >
        {pdfUrl ? (
          <PdfViewer
            fileUrl={pdfUrl}
            projectId={project.id}
            pageMeta={pageMetaDict}
            missingTypes={missingTypes}
            aiRooms={null}
            focusedPage={effectiveFocusedPage}
            focusedRoom={effectiveFocusedRoom}
            eksplikacija_source_page={project?._eksplikacija?.eksplikacija_source_page}
            onAiRoomClick={(room) => {
              // TODO: atidaryti modal'ą su pavadinimo / paskirties / ploto edit'u
              console.log('[ai-room] click:', room);
            }}
            pdfFile={pdfBlob}
            onSymbolCountResult={(symbolType, result) => {
              // Pridedam į projekto darbų sąrašą kaip naują eilutę.
              // Naudoja rangovas-kompatibilų pozicijos pavadinimą + kategoriją.
              const aprasymas = SYMBOL_LABELS[symbolType] || `Simbolių skaičius (${symbolType})`;
              const skyrius = SYMBOL_CATEGORIES[symbolType] || 'Kiti darbai';
              const kiekis = result?.count || (result?.matches?.length ?? 0);
              if (!kiekis) return;
              const darbai = [...(project.darbu_sarasas || [])];
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
              updateProject(project.id, { ...project, darbu_sarasas: darbai });
            }}
          />
        ) : pdfMissing ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <Layers className="w-12 h-12 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-foreground font-medium mb-1">Brėžinys nepasiekiamas</p>
            <p className="text-xs text-muted-foreground max-w-sm">
              Šis projektas sukurtas anksčiau ir PDF nebuvo išsaugotas. Sukurkite
              naują projektą, kad galėtumėte naudoti brėžinio matavimo įrankius.
            </p>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
            Krauname brėžinį…
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
