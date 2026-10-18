/**
 * ExportDropdown — top-right corner eksporto mygtukas su dropdown'u.
 * Visada matomas projekto puslapyje (pagal Q5 sprendimą).
 */

import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Download, FileSpreadsheet, FileText, ChevronDown, Loader2, Map as MapIcon } from 'lucide-react';
import { toast } from 'sonner';
import ExportFilterModal from './ExportFilterModal';
import { getFloorCount } from '@/lib/floorMultiplier';
import { markExported } from '@/lib/telemetry';
import { API_BASE as API } from '@/lib/apiBase';
import { sanitizeExportFilename } from '@/lib/exportFilename';
import { triggerDownload } from '@/lib/downloadBlob';
import { ensureSettingsPulled } from '@/lib/projectStore';
import { useConfirm } from '@/components/ui/confirm-provider';
import { fetchSamataTemplates, renderSamata, roomsForRender } from '@/lib/samataTemplateApi';
import { exportRows as templateExportRows, scaleExportRow } from '@/lib/samataTemplate';
import { resolveStaleRows } from '@/lib/mergeDarbuSarasas';
import { asksAboutPricesAfterDialog, exportLines, linesForExport } from '@/lib/exportLines';
import { listAssemblies } from '@/lib/assembliesApi';
import { effectiveKodas } from '@/lib/kodas';
import { DEFAULT_GROUPING, exportLinesWithParts, exportSheets } from '@/lib/exportGrouping';
import OverlayPdfDialog from './OverlayPdfDialog';
import { vatRateOf } from '@/lib/vatMode';

// Collect human-readable warnings from new + legacy schema sources.
// Backend `lt_sanity.warnings[]` (post-Phase 9 mirror) merges _lt_warnings
// AND pipeline warnings[] (e.g. eksplikacija-missing INFO). Legacy
// project.perspejimani is also passed through if present.
// Backend generate-excel expects {tekstas, kategorija} per warning.
// Map our {level, room, message} to that shape.
function collectWarnings(project) {
  // Sprint §AUDIT (2026-04-29): dedupe by `tekstas` — legacy projects have
  // BOTH lt_sanity.warnings AND project.perspejimani populated (Phase 9
  // mirror), so each warning appeared twice in exported Excel/PDF.
  const out = [];
  const seen = new Set();
  const push = (tekstas, kategorija) => {
    const t = (tekstas || '').trim();
    if (!t) return;
    const key = t.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ tekstas: t, kategorija });
  };
  const sanity = project.lt_sanity?.warnings || [];
  for (const w of sanity) {
    const kat = w.room ? `${w.level || 'INFO'} · ${w.room}` : (w.level || 'INFO');
    push(w.message, kat);
  }
  if (Array.isArray(project.perspejimani)) {
    for (const w of project.perspejimani) {
      if (typeof w === 'string') {
        push(w, 'INFO');
      } else {
        push(w.tekstas || w.message, w.kategorija || w.level || 'INFO');
      }
    }
  }
  return out;
}

// `grupavimas` (togal-v2 W8): another „Grupuoti pagal" than today's skyriai sends each line's room parts
// and the sheet names; the server groups them (api/export_grouping.py).
function buildPayload(project, allowedSkyriai = null, grupavimas = DEFAULT_GROUPING, kodasOf = null) {
  // allowedSkyriai: Set<string> | null. If null = include everything.
  // SM02: daugiabučiams kiekiai padauginti × aukštų skaičiaus.
  const floorCount = getFloorCount(project);
  // The printed lines live in lib/exportLines.js (2026-10-06), so the warnings
  // before sending — the Siųsti step, this dialog, the client link — count
  // exactly the rows this payload carries.
  const grouped = grupavimas && grupavimas !== DEFAULT_GROUPING;
  const lineOpts = { kodasOf };
  const eilutes = grouped
    ? exportLinesWithParts(project, allowedSkyriai, lineOpts) : exportLines(project, allowedSkyriai, lineOpts);
  const grouping = grouped ? { grupavimas, lapai: exportSheets(project) } : {};

  // V8 darbu_sarasas — primary source
  if (Array.isArray(project.darbu_sarasas) && project.darbu_sarasas.length > 0) {
    const projektas = floorCount > 1
      ? `${project.name} (× ${floorCount} aukštai)`
      : project.name;
    return {
      projektas,
      eilutes,
      patalpos: project.v8_rooms || project.patalpos || [],
      tipas: project.tipas || project.type || 'kz',
      perspejimani: collectWarnings(project),
      archetipas: project.archetipas || '',
      aukstu_skaicius: floorCount,
      ...grouping,
    };
  }
  // Fallback (KŽ projektai)
  return {
    projektas: floorCount > 1 ? `${project.name} (× ${floorCount} aukštai)` : project.name,
    eilutes,
    tipas: project.tipas || 'kz',
    aukstu_skaicius: floorCount,
  };
}

// `payloadOverride` (2026-09-05): the template-layout export sends rows already
// rendered in the contractor's own sections instead of buildPayload's list.
async function downloadFile(endpoint, project, filename, allowedSkyriai, extra = {}, payloadOverride = null) {
  // Sprint §AUDIT (2026-04-29): credentials: 'include' required after backend
  // export endpoints became auth-gated.
  // 2026-06-19: send the full branding block (logo + legal details) from global
  // Settings plus the per-export client/objektas so the deliverable reads as a
  // real LT pasiūlymas, not a raw quantity dump.
  // 2026-09-29: the settings live on the server; wait for this session's pull
  // so a logo and IBAN restored after a login are in the header.
  const s = await ensureSettingsPulled();
  const branding = {
    imone:        project.company_name || s.company_name || '',
    company_logo: s.company_logo || '',
    imones_kodas: s.imones_kodas || '',
    pvm_kodas:    s.pvm_kodas || '',
    adresas:      s.adresas || '',
    telefonas:    s.telefonas || '',
    el_pastas:    s.el_pastas || '',
    iban:         s.iban || '',
    vadovas:      s.vadovas || '',
    uzsakovas:    extra.uzsakovas || project.uzsakovas || '',
    objektas:     extra.objektas || project.objektas || '',
    pasiulymo_nr: extra.pasiulymo_nr || project.pasiulymo_nr || '',
  };
  // PVM (audit 2026-09-29): the mode the export dialog showed him — his pick or,
  // untouched, what lib/vatMode.js derives. Explicit, so the file prints it.
  // „Vidinė kopija" (audit exports-money-5, 2026-09-30): the notes are for him;
  // unless he ticked the option they are not even sent, so no server version
  // can put them into the file his client gets.
  // „Kodas" (togal-v2 W9): the row's effective code, only when he ticked the column.
  const suKodu = extra.su_kodu === true;
  let kodasOf = null;
  if (suKodu) {
    const { assemblies, kodai } = await listAssemblies().catch(() => ({ assemblies: [], kodai: {} }));
    kodasOf = (row) => effectiveKodas(row, assemblies, kodai);
  }
  const base = payloadOverride || buildPayload(project, allowedSkyriai, extra.grupavimas, kodasOf);
  const internalCopy = extra.vidine_kopija === true;
  const payload = {
    ...base,
    ...(base.perspejimani && !internalCopy ? { perspejimani: [] } : {}),
    ...branding,
    vat_mode: extra.vat_mode || project.vat_mode || '',
    // v3 M4: the rate the dialog showed (his pick, else the project's, else the
    // account default) — the server used to print 21 % whatever was chosen.
    vat_rate: vatRateOf({ vat_rate: extra.vat_rate ?? project.vat_rate }, s.vat_rate),
    vidine_kopija: internalCopy,
    // v3 M5: his internal copy gets „Pakeitimų žurnalas" — the server reads the
    // project's own change log (ownership-checked); the client's copy never asks.
    ...(internalCopy && project.id ? { project_id: project.id } : {}),
    ...(suKodu ? { su_kodu: true } : {}),
  };
  const res = await fetch(`${API}/${endpoint}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Klaida (${res.status})`);
  const blob = await res.blob();
  triggerDownload(blob, filename);
}

// `onProjectChange` (2026-09-29): stores his PVM choice on the project as
// `vat_mode`, so the on-screen totals and every export agree.
// `onGoToPrices(excludedSkyriai)` (2026-10-06): the dialog's „Įrašyti kainas" —
// closes the dialog and opens the Sąmata step at the first unpriced row. The
// sections he unticked come along (null for his own layout, whose sections are
// not ours), so the row it opens is one this document would print.
export default function ExportDropdown({ project, onProjectChange, onGoToPrices }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(null);
  const [filterFor, setFilterFor] = useState(null); // 'excel' | 'pdf' | 'excel-template' | null
  const ref = useRef(null);
  const confirm = useConfirm();
  const { t } = useTranslation();
  // The latest project for the undo of a stale-row choice (the toast outlives
  // this render).
  const latestProject = useRef(project);
  useEffect(() => { latestProject.current = project; });
  // His own layout (2026-09-05): offered only when the account has a template.
  // The rows are rendered ONCE when the menu item is chosen and reused for the
  // section list and the file, so the modal and the workbook agree.
  const [hasTemplate, setHasTemplate] = useState(false);
  const [templateRows, setTemplateRows] = useState(null);
  useEffect(() => {
    let alive = true;
    fetchSamataTemplates()
      .then((list) => { if (alive) setHasTemplate(list.length > 0); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  // Render the rows in his own layout; false when it failed (already told).
  const renderTemplate = async (rows) => {
    setLoading('excel-template');
    try {
      const body = await renderSamata(project.id, {
        rows: rows || [], rooms: roomsForRender(project),
      });
      setTemplateRows(body.eilutes || []);
      return true;
    } catch (e) {
      toast.error(`Nepavyko sudaryti sąmatos jūsų išdėstymu: ${e.message}`);
      return false;
    } finally {
      setLoading(null);
    }
  };

  const [overlayOpen, setOverlayOpen] = useState(false);
  const handle = async (action) => {
    setOpen(false);
    if (action === 'overlay-pdf') { setOverlayOpen(true); return; }
    if (action === 'excel-template') {
      if (await renderTemplate(project.darbu_sarasas)) setFilterFor(action);
      return;
    }
    setFilterFor(action);
  };

  // His answer to the stale-row line in the export dialog (audit
  // exports-money-4): the sąmata itself changes — the same edit as the row's own
  // „pašalinti" — so the screen and every later export agree. Undo in the toast.
  const applyRows = (rows) => {
    const next = { ...latestProject.current, darbu_sarasas: rows };
    onProjectChange?.(next);
    if (filterFor === 'excel-template') renderTemplate(rows);
  };
  const handleStaleChoice = (mode) => {
    const before = project.darbu_sarasas || [];
    const after = resolveStaleRows(before, mode);
    if (after === before) return;
    applyRows(after);
    toast.success(t(mode === 'carry' ? 'project.exportStale.carried' : 'project.exportStale.removed'), {
      duration: 6000,
      action: { label: t('project.exportStale.undo'), onClick: () => applyRows(before) },
    });
  };

  const handleConfirm = async ({ skyriai, format, uzsakovas, objektas, pasiulymo_nr, vat_mode, vat_rate, vidine_kopija, su_kodu, grupavimas }) => {
    // Prices (2026-10-06 walkthrough): the dialog he just confirmed already says
    // „N eilučių be kainos — klientas jas matys su 0,00 € suma", counted on these
    // very lines (lib/exportLines.js), so the two confirms that followed it —
    // „Nė viena pozicija neturi kainos", „N eilučių be kainos — eksportuoti vis
    // tiek?" — only repeated it. One case the line cannot cover still asks once:
    // a sąmata with no price at all whose document has no line with a quantity
    // (his own layout, every cell still blank) — asksAboutPricesAfterDialog.
    const lines = linesForExport(project, { format, templateRows, allowedSkyriai: skyriai });
    if (asksAboutPricesAfterDialog(project, lines)) {
      const ok = await confirm({
        title: t('project.send.noPriceAtAllTitle'),
        description: t('project.send.noPriceAtAllDesc'),
        confirmText: t('project.send.noPriceAtAllConfirm'),
        cancelText: t('project.send.noPriceAtAllCancel'),
      });
      if (!ok) return;
    }
    setLoading(format);
    try {
      const safeName = sanitizeExportFilename(project.name);
      const extra = { uzsakovas, objektas, pasiulymo_nr, vat_mode, vat_rate, vidine_kopija, su_kodu, grupavimas };
      if (format === 'excel') {
        await downloadFile('generate-excel', project, `${safeName}.xlsx`, skyriai, extra);
      } else if (format === 'excel-template') {
        // His sections, his order, his labels; a blank cell prints EMPTY (the
        // backend's `layout=template` branch), never „0,00 €".
        const floorCount = getFloorCount(project);
        const eilutes = templateExportRows(templateRows || [], skyriai)
          .map((r) => scaleExportRow(r, floorCount));
        const payload = {
          projektas: floorCount > 1 ? `${project.name} (× ${floorCount} aukštai)` : project.name,
          eilutes,
          patalpos: project.v8_rooms || project.patalpos || [],
          tipas: project.tipas || project.type || 'kz',
          perspejimani: collectWarnings(project),
          archetipas: project.archetipas || '',
          aukstu_skaicius: floorCount,
        };
        await downloadFile('generate-excel?layout=template', project, `${safeName}.xlsx`, skyriai, extra, payload);
      } else if (format === 'pdf') {
        await downloadFile('generate-pdf', project, `${safeName}.pdf`, skyriai, extra);
      }
      // Sprint §FIX-9 (2026-04-29): F2/F3 forms removed per user feedback.
      // Code preserved in docs/superpowers/backup-2026-04-29-f2-f3-forms.py
      // for re-enable once contractors confirm what's needed.
      markExported(project.id, format);
      toast.success('Failas atsisiųstas');
      setFilterFor(null);
    } catch (e) {
      toast.error(`Eksporto klaida: ${e.message}`);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(v => !v)}
        disabled={loading != null}
        title="Pasirinkti eksporto formatą — Excel sąmata arba PDF pasiūlymas klientui"
        aria-expanded={open}
        aria-haspopup="menu"
        className="inline-flex items-center gap-2 px-3.5 py-2 bg-foreground text-background rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
      >
        {loading
          ? <Loader2 className="w-4 h-4 animate-spin" />
          : <Download className="w-4 h-4" />}
        <span>Eksportuoti</span>
        <ChevronDown className="w-3.5 h-3.5 opacity-70" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-56 bg-card border border-border rounded-lg shadow-lg overflow-hidden z-20">
          <button
            onClick={() => handle('excel')}
            title="Excel byla su visomis eilutėmis, kiekiais, kainomis ir suvestine — galėsite toliau redaguoti"
            className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-muted text-left text-sm transition-colors"
          >
            <FileSpreadsheet className="w-4 h-4 text-muted-foreground" />
            <div className="flex-1">
              <div className="font-medium text-foreground">Excel (.xlsx)</div>
              <div className="text-meta text-muted-foreground">Sąmata su skyriais ir kainomis</div>
            </div>
          </button>
          {hasTemplate && (
            <button
              onClick={() => handle('excel-template')}
              title="Jūsų skyriai ir eilučių pavadinimai kaip jūsų sąmatose; tušti langeliai lieka tušti"
              className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-muted text-left text-sm border-t border-border transition-colors"
            >
              <FileSpreadsheet className="w-4 h-4 text-muted-foreground" />
              <div className="flex-1">
                <div className="font-medium text-foreground">Excel — kaip mano sąmatose</div>
                <div className="text-meta text-muted-foreground">Jūsų skyriai ir pavadinimai, tušti langeliai tušti</div>
              </div>
            </button>
          )}
          <button
            onClick={() => handle('pdf')}
            title="Spausdintinas pasiūlymas su jūsų įmonės duomenimis ir logotipu iš Nustatymų"
            className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-muted text-left text-sm border-t border-border transition-colors"
          >
            <FileText className="w-4 h-4 text-muted-foreground" />
            <div className="flex-1">
              <div className="font-medium text-foreground">PDF pasiūlymas</div>
              <div className="text-meta text-muted-foreground">Spausdintinas komercinis pasiūlymas</div>
            </div>
          </button>
          {project?.has_pdf !== false && project?.id && (
            <button
              onClick={() => handle('overlay-pdf')}
              title="Brėžinio lapai su patalpų kontūrais, matavimais ir skaičiavimais bei legenda kiekviename lape"
              className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-muted text-left text-sm border-t border-border transition-colors"
            >
              <MapIcon className="w-4 h-4 text-muted-foreground" />
              <div className="flex-1">
                <div className="font-medium text-foreground">PDF su žymėjimais</div>
                <div className="text-meta text-muted-foreground">Brėžiniai su kontūrais, matavimais ir legenda</div>
              </div>
            </button>
          )}
          {/* Sprint §FIX-9 (2026-04-29): F2/F3 forms removed per user.
              Will return after contractor feedback — code in
              docs/superpowers/backup-2026-04-29-f2-f3-forms.py */}
        </div>
      )}

      {overlayOpen && <OverlayPdfDialog project={project} onClose={() => setOverlayOpen(false)} />}

      {filterFor && (
        <ExportFilterModal
          project={project}
          format={filterFor}
          rows={filterFor === 'excel-template' ? templateRows : null}
          loading={loading === filterFor}
          onCancel={() => { if (loading == null) setFilterFor(null); }}
          onConfirm={handleConfirm}
          onVatModeChange={(mode) => onProjectChange?.({ ...project, vat_mode: mode })}
          onVatRateChange={(rate) => onProjectChange?.({ ...project, vat_rate: rate })}
          onStaleChoice={onProjectChange ? handleStaleChoice : undefined}
          onGoToPrices={onGoToPrices ? (excluded) => {
            setFilterFor(null);
            onGoToPrices(filterFor === 'excel-template' ? null : excluded);
          } : undefined}
        />
      )}
    </div>
  );
}
