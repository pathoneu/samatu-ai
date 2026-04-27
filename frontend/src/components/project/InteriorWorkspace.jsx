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
import { getPdfUrl, getPdfBlob } from '@/lib/pdfStore';
import { updateProject } from '@/lib/projectStore';

const SYMBOL_LABELS = {
  rozetes: 'Rozetės/jungiklio komutavimas',
  jungikliai: 'Rozetės/jungiklio komutavimas',
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

export default function InteriorWorkspace({ project }) {
  const [pdfUrl, setPdfUrl] = useState(null);
  const [pdfBlob, setPdfBlob] = useState(null);  // Diena 6: V9 click-to-count'ui
  const [splitRatio, setSplitRatio] = useState(65);
  const [pdfMissing, setPdfMissing] = useState(false);

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

  const pageMetaDict = useMemo(() => {
    const dict = {};
    (project.v8_pages || []).forEach(p => {
      dict[p.page] = { label: p.label, type: p.type, confidence: p.confidence };
    });
    return dict;
  }, [project.v8_pages]);

  return (
    <div className="flex h-[calc(100vh-180px)] min-h-[600px] border border-border rounded-lg overflow-hidden bg-background">
      {/* LEFT: PDF + AI overlay (Togal-style) */}
      <div className="flex flex-col border-r border-border" style={{ width: `${splitRatio}%` }}>
        {pdfUrl ? (
          <PdfViewer
            fileUrl={pdfUrl}
            projectId={project.id}
            pageMeta={pageMetaDict}
            aiRooms={project.v8_rooms || project.patalpos}
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
                  source: 'AI Vision (click-to-count)',
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
                  source: 'AI Vision (click-to-count)',
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

      {/* Resizer */}
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

      {/* RIGHT: Kompaktinė sąmatos panelė */}
      <div style={{ width: `${100 - splitRatio}%` }} className="overflow-hidden">
        <WorkspacePanel project={project} />
      </div>
    </div>
  );
}
