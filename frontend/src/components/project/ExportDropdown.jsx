/**
 * ExportDropdown — top-right corner eksporto mygtukas su dropdown'u.
 * Visada matomas projekto puslapyje (pagal Q5 sprendimą).
 */

import { useState, useRef, useEffect } from 'react';
import { Download, FileSpreadsheet, FileText, ChevronDown, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import ExportFilterModal from './ExportFilterModal';
import { getFloorCount } from '@/lib/floorMultiplier';
import { API_BASE as API } from '@/lib/apiBase';
import { sanitizeExportFilename } from '@/lib/exportFilename';
import { triggerDownload } from '@/lib/downloadBlob';
import { useConfirm } from '@/components/ui/confirm-provider';
import { fetchSamataTemplates, renderSamata, roomsForRender } from '@/lib/samataTemplateApi';
import { exportRows as templateExportRows } from '@/lib/samataTemplate';

// "1 eilutė / 2 eilutės / 11 eilučių" — LT plural, so the unpriced-lines
// warning doesn't read like machine output.
function ltEilutes(n) {
  const d10 = n % 10, d100 = n % 100;
  if (d10 === 1 && d100 !== 11) return `${n} eilutė`;
  if (d10 >= 2 && d10 <= 9 && (d100 < 10 || d100 > 20)) return `${n} eilutės`;
  return `${n} eilučių`;
}

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

function buildPayload(project, allowedSkyriai = null) {
  // allowedSkyriai: Set<string> | null. If null = include everything.
  const keep = (skyrius) => !allowedSkyriai || allowedSkyriai.has(skyrius);
  // SM02: daugiabučiams kiekiai padauginti × aukštų skaičiaus.
  const floorCount = getFloorCount(project);
  const mult = (n) => (n || 0) * floorCount;

  // V8 darbu_sarasas — primary source
  if (Array.isArray(project.darbu_sarasas) && project.darbu_sarasas.length > 0) {
    const projektas = floorCount > 1
      ? `${project.name} (× ${floorCount} aukštai)`
      : project.name;
    return {
      projektas,
      eilutes: project.darbu_sarasas
        .filter(it => (it.kiekis || 0) > 0)
        .map((it, i) => {
          const kiekis = mult(it.kiekis);
          return {
            nr: String(it.eil_nr || i + 1),
            aprasymas: it.aprasymas || '',
            mato_vnt: it.mato_vnt || it.vnt || '',
            kiekis,
            kaina: it.kaina || 0,
            suma: kiekis * (it.kaina || 0),
            skyrius: it.skyrius || it.kategorija || 'Apdaila',
            confidence: it.confidence || 'medium',
          };
        })
        .filter(it => keep(it.skyrius)),
      patalpos: project.v8_rooms || project.patalpos || [],
      tipas: project.tipas || project.type || 'kz',
      perspejimani: collectWarnings(project),
      archetipas: project.archetipas || '',
      aukstu_skaicius: floorCount,
    };
  }
  // Fallback (KŽ projektai)
  return {
    projektas: floorCount > 1 ? `${project.name} (× ${floorCount} aukštai)` : project.name,
    eilutes: (project.rows || [])
      .map(r => {
        const kiekis = mult(r.kiekis);
        return {
          nr: r.nr || '', aprasymas: r.aprasymas || '',
          mato_vnt: r.mato_vnt || '',
          kiekis,
          kaina: r.kaina || 0,
          suma: kiekis * (r.kaina || 0),
          skyrius: r.skyrius || '',
        };
      })
      .filter(it => keep(it.skyrius || '')),
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
  let s = {};
  try { s = JSON.parse(localStorage.getItem('samatu_settings') || '{}'); } catch { /* ignore */ }
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
  const payload = { ...(payloadOverride || buildPayload(project, allowedSkyriai)), ...branding };
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

export default function ExportDropdown({ project }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(null);
  const [filterFor, setFilterFor] = useState(null); // 'excel' | 'pdf' | 'excel-template' | null
  const ref = useRef(null);
  const confirm = useConfirm();
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

  const handle = async (action) => {
    setOpen(false);
    if (action === 'excel-template') {
      setLoading('excel-template');
      try {
        const body = await renderSamata(project.id, {
          rows: project.darbu_sarasas || [], rooms: roomsForRender(project),
        });
        setTemplateRows(body.eilutes || []);
        setFilterFor(action);
      } catch (e) {
        toast.error(`Nepavyko sudaryti sąmatos jūsų išdėstymu: ${e.message}`);
      } finally {
        setLoading(null);
      }
      return;
    }
    setFilterFor(action);
  };

  const handleConfirm = async ({ skyriai, format, uzsakovas, objektas, pasiulymo_nr }) => {
    // Guard: exporting a sąmata where every line is 0,00 € sends the client a
    // quantities-only "free" quote by accident. Nudge to price first. (2026-06-19)
    // Check ALL candidate lists, not just pozicijos: interior prices live in
    // darbu_sarasas, and a Prielaidos recompute leaves project.pozicijos unpriced
    // — so reading pozicijos alone false-warns on a fully-priced export.
    const priced = [project.darbu_sarasas, project.rows, project.pozicijos]
      .filter(Array.isArray).flat();
    const anyPrice = priced.some((r) => Number(r?.kaina) > 0);
    if (priced.length > 0 && !anyPrice) {
      const ok = await confirm({
        title: 'Eksportuoti be kainų?',
        description: 'Nė viena pozicija neturi kainos — dokumente bus tik kiekiai, o suma 0,00 €. Rekomenduojama pirma pritaikyti kainyną.',
        confirmText: 'Eksportuoti vis tiek',
        cancelText: 'Grįžti ir įvesti kainas',
      });
      if (!ok) return;
    }
    // Partial-price guard (2026-07-28 walkthrough): the check above only fires
    // when EVERY line is unpriced, so a sąmata where 3 of 40 positions still sat
    // at 0,00 € went to the client silently. Count on the payload actually being
    // exported (skyriai filter applied, kiekis = 0 placeholder rows are dropped
    // by buildPayload, so they can't inflate the warning). In his own layout the
    // rows are the rendered ones; blank cells are by design and are not counted.
    const exportedRows = (format === 'excel-template'
      ? templateExportRows(templateRows || [], skyriai)
      : (buildPayload(project, skyriai).eilutes || []))
      .filter((r) => (r.kiekis || 0) > 0);
    const unpricedRows = exportedRows.filter((r) => !(Number(r.kaina) > 0));
    if (unpricedRows.length > 0 && unpricedRows.length < exportedRows.length) {
      const ok = await confirm({
        title: `${ltEilutes(unpricedRows.length)} be kainos — eksportuoti vis tiek?`,
        description: 'Šios pozicijos dokumente bus su 0,00 € suma. Galite grįžti ir įvesti kainas arba pritaikyti kainyną.',
        confirmText: 'Eksportuoti',
        cancelText: 'Atšaukti',
      });
      if (!ok) return;
    }
    setLoading(format);
    try {
      const safeName = sanitizeExportFilename(project.name);
      const extra = { uzsakovas, objektas, pasiulymo_nr };
      if (format === 'excel') {
        await downloadFile('generate-excel', project, `${safeName}.xlsx`, skyriai, extra);
      } else if (format === 'excel-template') {
        // His sections, his order, his labels; a blank cell prints EMPTY (the
        // backend's `layout=template` branch), never „0,00 €".
        const floorCount = getFloorCount(project);
        const eilutes = templateExportRows(templateRows || [], skyriai).map((r) => (
          r.kiekis == null ? r : { ...r, kiekis: r.kiekis * floorCount, suma: r.kiekis * floorCount * (r.kaina || 0) }
        ));
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
              <div className="text-[11px] text-muted-foreground">Sąmata su skyriais ir kainomis</div>
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
                <div className="text-[11px] text-muted-foreground">Jūsų skyriai ir pavadinimai, tušti langeliai tušti</div>
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
              <div className="text-[11px] text-muted-foreground">Spausdintinas komercinis pasiūlymas</div>
            </div>
          </button>
          {/* Sprint §FIX-9 (2026-04-29): F2/F3 forms removed per user.
              Will return after contractor feedback — code in
              docs/superpowers/backup-2026-04-29-f2-f3-forms.py */}
        </div>
      )}

      {filterFor && (
        <ExportFilterModal
          project={project}
          format={filterFor}
          rows={filterFor === 'excel-template' ? templateRows : null}
          loading={loading === filterFor}
          onCancel={() => { if (loading == null) setFilterFor(null); }}
          onConfirm={handleConfirm}
        />
      )}
    </div>
  );
}
