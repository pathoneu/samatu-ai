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
import { X, FileSpreadsheet, FileText, Loader2 } from 'lucide-react';
import {
  exportSelectionKey,
  parseExcludedSections,
  serializeExcludedSections,
  selectedFor,
  toggleSection,
} from '@/lib/exportSectionSelection';

// The persisted value is the set of EXPLICITLY EXCLUDED skyriai, so a skyrius
// that shows up later (re-extraction, recompute, a new Matavimai line) is
// included by default instead of being silently dropped from the export.
function loadExcluded(projectId) {
  try {
    return parseExcludedSections(localStorage.getItem(exportSelectionKey(projectId)));
  } catch {
    return new Set();
  }
}

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
}) {
  const { t } = useTranslation();
  // Build unique-skyrius list with row count + total kiekis per skyrius.
  const sections = useMemo(() => {
    const map = new Map();
    const items = rows
      ? rows
      : (project.darbu_sarasas || []).filter(it => (it.kiekis || 0) > 0);
    for (const it of items) {
      const s = it.skyrius || it.kategorija || 'Kiti darbai';
      const cur = map.get(s) || { count: 0 };
      cur.count += 1;
      map.set(s, cur);
    }
    return [...map.entries()]
      .map(([name, info]) => ({ name, ...info }))
      .sort((a, b) => a.name.localeCompare(b.name, 'lt'));
  }, [project.darbu_sarasas, rows]);

  // State = what the user explicitly UNCHECKED. The checked set is derived from
  // the sections that exist right now, so no reconciliation effect is needed and
  // a newly-appearing skyrius can never arrive pre-unchecked.
  const [excluded, setExcluded] = useState(() => loadExcluded(project.id));
  const selected = useMemo(
    () => selectedFor(sections.map(s => s.name), excluded),
    [sections, excluded],
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
                      <span className="flex-1 text-sm text-foreground">{s.name}</span>
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
            disabled={loading || noneChecked}
            title={noneChecked
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
