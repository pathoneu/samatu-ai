/**
 * ExportFilterModal — pre-export skyrius (section) picker (Phase 14 / QW04).
 *
 * Vartotojas prieš atsisiųsdamas Excel/PDF pažymi, kuriuos skyrius nori
 * įtraukti. Numatyta — visi pažymėti. Pasirinkimas išsaugomas
 * localStorage'e per projektą, kad nereikėtų kiekvieną kartą tikrinti.
 */

import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { ltCount } from '@/lib/ltPlural';
import { VAT_REVERSE, VAT_STANDARD, vatChoice } from '@/lib/vatMode';
import { staleRowsForExport, staleRowCarryTargets } from '@/lib/mergeDarbuSarasas';
import { exportSections, linesForExport, linesWithoutPrice } from '@/lib/exportLines';
import { X, FileSpreadsheet, FileText, Loader2 } from 'lucide-react';
import {
  exportSelectionKey,
  loadExcludedSections,
  serializeExcludedSections,
  selectedFor,
  toggleSection,
} from '@/lib/exportSectionSelection';

// The persisted value is the set of EXPLICITLY EXCLUDED skyriai, so a skyrius
// that shows up later (re-extraction, recompute, a new Matavimai line) is
// included by default instead of being silently dropped from the export.
// Reading it lives in lib/exportSectionSelection.js — the Siųsti step counts
// with the same stored choice.
function saveExcluded(projectId, excluded) {
  try {
    localStorage.setItem(exportSelectionKey(projectId), serializeExcludedSections(excluded));
  } catch {
    // ignored — non-critical
  }
}

export default function ExportFilterModal({
  project,
  format, // 'excel' | 'pdf' | 'excel-template'
  loading,
  onCancel,
  onConfirm,
  // 'excel-template' (2026-09-05): the rows already rendered in the
  // contractor's own layout. His sections replace ours in the list, and a
  // section whose rows are all still blank stays listed — blank is a state of
  // his sheet, not a reason to drop the section.
  rows = null,
  // PVM (audit 2026-09-29): called with 'standard' | 'reverse_vat' when he
  // picks one; the parent stores it on the project as `vat_mode`.
  onVatModeChange,
  // Stale rows (audit exports-money-4, 2026-09-30): called with 'remove' |
  // 'carry' when he answers the stale-row line; the parent edits the sąmata.
  onStaleChoice,
  // „Įrašyti kainas" (2026-10-06): called with the sections he unticked; the
  // parent closes this dialog and opens the first unpriced row. Optional —
  // without it the line still says how many rows go out without a price.
  onGoToPrices,
}) {
  const { t } = useTranslation();
  // The sections with their row counts — the lines this document prints, grouped
  // by the very name the export's section filter checks (lib/exportLines.js
  // exportSections). 2026-10-06: this list named a row without a section
  // „Kiti darbai" while the export filed it under „Apdaila", so with every
  // section ticked the row could still be left out of the file silently. His own
  // layout's rows are all listed, blank cells too — blank is a state of his sheet.
  const sections = useMemo(
    () => exportSections(linesForExport(project, { format, templateRows: rows })),
    [project, format, rows],
  );

  // State = what the user explicitly UNCHECKED. The checked set is derived from
  // the sections that exist right now, so no reconciliation effect is needed and
  // a newly-appearing skyrius can never arrive pre-unchecked.
  const [excluded, setExcluded] = useState(() => loadExcludedSections(project.id));
  const selected = useMemo(
    () => selectedFor(sections.map(s => s.name), excluded),
    [sections, excluded],
  );

  // Rows this document prints with a quantity and no price — 0,00 € on paper.
  // Counted on the very lines the export sends (lib/exportLines.js), so it
  // follows the ticked sections. Says it; never blocks the export.
  const unpricedCount = useMemo(
    () => linesWithoutPrice(linesForExport(project, {
      format, templateRows: rows, allowedSkyriai: selected,
    })).length,
    [project, format, rows, selected],
  );

  // Per-export client/objektas (2026-06-19) — rendered into the PDF/Excel header
  // so the deliverable reads as a real pasiūlymas. Defaults from the project.
  const [uzsakovas, setUzsakovas] = useState(project.uzsakovas || '');
  const [objektas, setObjektas] = useState(project.objektas || project.name || '');

  // What the document will print, and his switch. Until he picks, a reverse
  // VAT that came from the drawing label is named as such (lib/vatMode.js).
  const [vatMode, setVatMode] = useState(() => vatChoice(project).mode);
  const [vatFromLabel, setVatFromLabel] = useState(() => vatChoice(project).fromLabel);
  const chooseVat = (mode) => {
    setVatMode(mode);
    setVatFromLabel(false);
    onVatModeChange?.(mode);
  };

  // A row the last recompute could not reproduce keeps its OLD quantity; beside
  // its re-tiered successor the export billed the same work twice. He answers
  // once per dialog: remove / keep (or carry the price when it clearly belongs
  // to the new row). Export waits for the answer; nothing changes without it.
  const staleCount = useMemo(
    () => staleRowsForExport(project.darbu_sarasas).length, [project.darbu_sarasas]);
  const carryCount = useMemo(
    () => staleRowCarryTargets(project.darbu_sarasas).size, [project.darbu_sarasas]);
  const [staleKept, setStaleKept] = useState(false);
  const staleOpen = staleCount > 0 && !staleKept;

  // „Vidinė kopija" (audit exports-money-5): the notes sheet is for him, so the
  // client workbook leaves it out unless he ticks this. Excel only, never kept.
  const [internalCopy, setInternalCopy] = useState(false);

  const allChecked = selected.size === sections.length;
  const noneChecked = selected.size === 0;

  const toggle = (name) => {
    setExcluded(prev => toggleSection(prev, name));
  };

  const toggleAll = () => {
    setExcluded(prev => {
      if (!allChecked) return new Set([...prev].filter(n => !sections.some(s => s.name === n)));
      const next = new Set(prev);
      for (const s of sections) next.add(s.name);
      return next;
    });
  };

  const handleConfirm = () => {
    saveExcluded(project.id, excluded);
    onConfirm({
      skyriai: selected,
      format,
      uzsakovas: uzsakovas.trim(),
      objektas: objektas.trim(),
      vat_mode: vatMode,
      vidine_kopija: format !== 'pdf' && internalCopy,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-md max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            {format !== 'pdf'
              ? <FileSpreadsheet className="w-4 h-4 text-muted-foreground" />
              : <FileText className="w-4 h-4 text-muted-foreground" />}
            <h2 className="text-sm font-semibold text-foreground">
              Eksportuoti {format !== 'pdf' ? 'Excel' : 'PDF'} — pasirinkti skyriai
            </h2>
          </div>
          <button onClick={onCancel} disabled={loading}
            title="Užverti neeksportavus" aria-label="Užverti"
            className="text-muted-foreground hover:text-foreground disabled:opacity-50">
            <X className="w-4 h-4" />
          </button>
        </div>

        {staleCount > 0 && (
          <div className="px-5 py-3 border-b border-border" role="status">
            {staleOpen ? (
              <>
                <p className="text-[12px]" style={{ color: 'hsl(var(--conf-med))' }}>
                  {t('project.exportStale.line', { count: staleCount })}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {carryCount > 0 && onStaleChoice && (
                    <button type="button" onClick={() => onStaleChoice('carry')} disabled={loading}
                      title={t('project.exportStale.carryTitle')}
                      className="px-2.5 py-1 text-xs rounded border border-border bg-background hover:bg-muted disabled:opacity-50">
                      {t('project.exportStale.carry', { count: carryCount })}
                    </button>
                  )}
                  {onStaleChoice && (
                    <button type="button" onClick={() => onStaleChoice('remove')} disabled={loading}
                      title={t('project.exportStale.removeTitle')}
                      className="px-2.5 py-1 text-xs rounded border border-border bg-background hover:bg-muted disabled:opacity-50">
                      {t('project.exportStale.remove')}
                    </button>
                  )}
                  <button type="button" onClick={() => setStaleKept(true)} disabled={loading}
                    title={t('project.exportStale.keepTitle')}
                    className="px-2.5 py-1 text-xs rounded border border-border bg-background hover:bg-muted disabled:opacity-50">
                    {t('project.exportStale.keep')}
                  </button>
                </div>
              </>
            ) : (
              <p className="text-[12px] text-muted-foreground">{t('project.exportStale.kept')}</p>
            )}
          </div>
        )}

        <div className="px-5 py-3 border-b border-border grid grid-cols-2 gap-2">
          <div>
            <label className="text-[11px] text-muted-foreground">Užsakovas</label>
            <input
              value={uzsakovas}
              onChange={e => setUzsakovas(e.target.value)}
              placeholder="UAB Klientas"
              aria-label="Užsakovas"
              title="Kam skirtas pasiūlymas — bus atspausdinta dokumento antraštėje"
              className="mt-0.5 w-full h-8 px-2 text-sm bg-background border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>
          <div>
            <label className="text-[11px] text-muted-foreground">Objektas</label>
            <input
              value={objektas}
              onChange={e => setObjektas(e.target.value)}
              placeholder="Objekto pavadinimas / adresas"
              aria-label="Objektas"
              title="Statybos objektas — bus atspausdinta dokumento antraštėje"
              className="mt-0.5 w-full h-8 px-2 text-sm bg-background border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>
        </div>

        <div className="px-5 py-3 border-b border-border">
          <p className="text-[11px] text-muted-foreground">{t('project.vatChoice.title')}</p>
          <div role="radiogroup" aria-label={t('project.vatChoice.title')} className="mt-1 space-y-0.5">
            {[
              [VAT_STANDARD, 'standard', 'standardDesc'],
              [VAT_REVERSE, 'reverse', 'reverseDesc'],
            ].map(([mode, label, desc]) => (
              <label key={mode}
                className="flex items-start gap-2.5 px-2 py-1.5 rounded hover:bg-muted/40 cursor-pointer transition-colors">
                <input
                  type="radio"
                  name="vat_mode"
                  value={mode}
                  checked={vatMode === mode}
                  onChange={() => chooseVat(mode)}
                  className="mt-0.5 w-4 h-4 accent-foreground"
                />
                <span className="flex-1">
                  <span className="block text-sm text-foreground">{t(`project.vatChoice.${label}`)}</span>
                  <span className="block text-[12px] text-muted-foreground">{t(`project.vatChoice.${desc}`)}</span>
                </span>
              </label>
            ))}
          </div>
          {vatFromLabel && (
            <p className="mt-1 px-2 text-[12px]" style={{ color: 'hsl(var(--conf-med))' }}>
              {t('project.vatChoice.fromLabel')}
            </p>
          )}
        </div>

        {format !== 'pdf' && (
          <div className="px-5 py-3 border-b border-border">
            <label className="flex items-start gap-2.5 px-2 py-1.5 rounded hover:bg-muted/40 cursor-pointer transition-colors">
              <input
                type="checkbox"
                checked={internalCopy}
                onChange={e => setInternalCopy(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-foreground"
              />
              <span className="flex-1">
                <span className="block text-sm text-foreground">{t('project.exportInternal.label')}</span>
                <span className="block text-[12px] text-muted-foreground">{t('project.exportInternal.desc')}</span>
              </span>
            </label>
          </div>
        )}

        <div className="px-5 py-3 border-b border-border flex items-center justify-between">
          <button
            onClick={toggleAll}
            title="Pažymėti arba nužymėti visus skyrius iš karto"
            className="text-xs text-foreground hover:underline"
          >
            {allChecked ? 'Nužymėti visus' : 'Pažymėti visus'}
          </button>
          <span className="text-xs text-muted-foreground">
            Pažymėta: <strong className="tabular-nums">{selected.size}</strong> / {sections.length}
          </span>
        </div>

        <div className="overflow-y-auto px-3 py-2 flex-1">
          {sections.length === 0 ? (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">
              Šiame projekte nėra eilučių, kurias būtų galima eksportuoti.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {sections.map(s => {
                const checked = selected.has(s.name);
                return (
                  <li key={s.name}>
                    <label className="flex items-center gap-3 px-2 py-2 rounded hover:bg-muted/40 cursor-pointer transition-colors">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(s.name)}
                        className="w-4 h-4 accent-foreground"
                      />
                      <span className="flex-1 text-sm text-foreground">{s.name || 'Be skyriaus'}</span>
                      <span className="text-[11px] text-muted-foreground tabular-nums">
                        {ltCount(s.count, 'eilutė', 'eilutės', 'eilučių')}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {unpricedCount > 0 && (
          <div className="px-5 py-3 border-t border-border" role="status">
            <p className="text-[12px]" style={{ color: 'hsl(var(--conf-med))' }}>
              {t('project.send.checkNoPrice', { count: unpricedCount })}
            </p>
            {onGoToPrices && (
              <button type="button" onClick={() => onGoToPrices(excluded)} disabled={loading}
                title={t('project.send.goToPricesTitle')}
                className="mt-2 px-2.5 py-1 text-xs rounded border border-border bg-background hover:bg-muted disabled:opacity-50">
                {t('project.send.goToPrices')}
              </button>
            )}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border">
          <button
            onClick={onCancel}
            disabled={loading}
            title="Grįžti neatsisiuntus failo"
            className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground disabled:opacity-50"
          >
            Atšaukti
          </button>
          <button
            onClick={handleConfirm}
            disabled={loading || noneChecked || staleOpen}
            title={staleOpen
              ? t('project.exportStale.blockedTitle')
              : noneChecked
              ? 'Pažymėkite bent vieną skyrių'
              : `Sugeneruoti ir atsisiųsti ${format !== 'pdf' ? 'Excel' : 'PDF'} failą su pažymėtais skyriais`}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-foreground text-background rounded text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {loading
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : (format !== 'pdf'
                  ? <FileSpreadsheet className="w-3.5 h-3.5" />
                  : <FileText className="w-3.5 h-3.5" />)}
            Eksportuoti
          </button>
        </div>
      </div>
    </div>
  );
}
