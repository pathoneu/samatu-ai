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
import { Layers, Upload } from 'lucide-react';
// PlanViewer is the legacy single-page PDF viewer; replaced by AnnotatorView
// (multi-page Fabric canvas) for the Brėžinys tab as of 2026-06-02. Kept
// importable for now in case a feature flag wants to A/B back.
import AnnotatorView from '@/components/annotator/AnnotatorView';
import WorkspacePanel from './WorkspacePanel';
import OnboardingTooltips from './OnboardingTooltips';
import { getPdfUrl, getPdfBlob, savePdf } from '@/lib/pdfStore';
import { updateProject } from '@/lib/projectStore';
import { buildPageMetaDict, missingInteriorTypes } from '@/lib/pageTypes';

// SYMBOL_LABELS / SYMBOL_CATEGORIES tables were used by the old PlanViewer's
// click-to-count flow that pushed counted symbols into project.darbu_sarasas.
// AnnotatorView's symbol palette + persistence handles this differently now;
// the tables are removed with the old wiring.

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
  const [attachingPdf, setAttachingPdf] = useState(false);
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

  // 2026-06-02: Brėžinys tab is now the multi-page Fabric viewer (AnnotatorView)
  // with its OWN built-in sidebar (KŽ santrauka + room list + measurements).
  // The legacy 70/30 split with PlanViewer + WorkspacePanel was removed — the
  // contractor's editing UI lives in the Kiekiai tab (ProjectMainView). This
  // tab is now purely for visual takeoff work.
  return (
    <div className="h-[calc(100vh-180px)] min-h-[600px] border border-border rounded-lg overflow-hidden bg-background relative">
      <OnboardingTooltips />
      {pdfUrl ? (
        <AnnotatorView
          projectId={project.id}
          pdfUrl={pdfUrl}
          embedded
          initialPage={effectiveFocusedPage || 2}
        />
      ) : pdfMissing ? (
        <div className="h-full flex flex-col items-center justify-center p-8 text-center">
          <Layers className="w-12 h-12 text-muted-foreground/40 mb-3" />
          <p className="text-sm text-foreground font-medium mb-1">Brėžinys nepasiekiamas</p>
          <p className="text-xs text-muted-foreground max-w-sm">
            Šis projektas sukurtas anksčiau ir PDF nebuvo išsaugotas. Sukurkite
            naują projektą, kad galėtumėte naudoti brėžinio matavimo įrankius.
          </p>
          <label
            className="mt-4 inline-flex items-center gap-2 px-3 py-2 rounded border border-border bg-card hover:bg-muted/50 cursor-pointer text-sm text-foreground transition-colors"
          >
            <Upload className="w-4 h-4" />
            {attachingPdf ? 'Prisegama…' : 'Prisegti PDF prie projekto'}
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
                  await savePdf(project.id, file);
                  const [u, b] = await Promise.all([getPdfUrl(project.id), getPdfBlob(project.id)]);
                  setPdfUrl(u);
                  setPdfBlob(b);
                  setPdfMissing(!u);
                  onProjectChange?.({ ...project, pdf_name: file.name, has_pdf: true });
                } finally {
                  setAttachingPdf(false);
                  event.target.value = '';
                }
              }}
            />
          </label>
        </div>
      ) : (
        <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
          Krauname brėžinį…
        </div>
      )}
    </div>
  );
}
