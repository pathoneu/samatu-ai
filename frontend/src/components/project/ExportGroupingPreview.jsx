/**
 * ExportGroupingPreview — „Peržiūra": the first rows of the Excel exactly as the chosen grouping prints them
 * (togal-v2 W8). The rows come from the server's dry run (POST …/export-excel/preview), the same function
 * that writes the workbook, so the preview cannot disagree with the file. Each row says whether its number
 * is the program's or his own.
 */
import { useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { fetchExportPreview } from '@/lib/exportApi';
import { exportLinesWithParts, exportSheets } from '@/lib/exportGrouping';
import { ltNumber } from '@/lib/ledger';
import { ltCount } from '@/lib/ltPlural';

const PREVIEW_ROWS = 20;

export default function ExportGroupingPreview({ project, grupavimas, allowedSkyriai }) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const payload = useMemo(() => ({
    grupavimas,
    eilutes: exportLinesWithParts(project, allowedSkyriai),
    patalpos: project.v8_rooms || project.patalpos || [],
    lapai: exportSheets(project),
    limit: PREVIEW_ROWS,
  }), [project, grupavimas, allowedSkyriai]);

  useEffect(() => {
    const ctrl = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    const t = setTimeout(() => {
      fetchExportPreview(project.id, payload, { signal: ctrl.signal })
        .then((data) => setState({ loading: false, data, error: null }))
        .catch((e) => { if (!ctrl.signal.aborted) setState({ loading: false, data: null, error: e.message }); });
    }, 250);
    return () => { clearTimeout(t); ctrl.abort(); };
  }, [project.id, payload]);

  const { loading, data, error } = state;
  const shown = data ? data.rows.filter((r) => r.kind === 'row').length : 0;

  return (
    <div className="px-5 py-3 border-b border-border" aria-live="polite">
      <div className="flex items-center justify-between">
        <p className="text-[11px] text-muted-foreground">Peržiūra — taip atrodys Excel</p>
        {loading && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" aria-label="Kraunama" />}
      </div>
      {error && <p className="mt-1 text-[12px] text-destructive">Peržiūros nepavyko gauti: {error}</p>}
      {data && (
        <>
          <div className="mt-1.5 max-h-56 overflow-y-auto border border-border rounded-sm">
            <table className="w-full text-[11px] tabular-nums">
              <tbody>
                {data.rows.map((r, i) => (r.kind === 'heading' ? (
                  <tr key={`h${i}`} className="bg-muted">
                    <td colSpan={4} className="px-2 py-1 font-medium text-foreground">{r.label}</td>
                  </tr>
                ) : (
                  <tr key={`r${i}`} className="border-t border-border">
                    <td className="pl-1.5 pr-1 py-1 align-top w-1">
                      <span
                        title={r.kaip_gauta}
                        className="block w-1 h-3.5 rounded-sm"
                        style={{ background: r.programos ? 'hsl(var(--conf-med))' : 'hsl(var(--accent-2))' }}
                      />
                    </td>
                    <td className={`px-1 py-1 ${r.dalis === 'under' || r.dalis === 'over' ? 'italic text-muted-foreground' : 'text-foreground'}`}>
                      <span className="text-muted-foreground mr-1">{r.nr}</span>{r.aprasymas}
                      <span className="block text-[10px] text-muted-foreground">{r.kaip_gauta}</span>
                    </td>
                    <td className="px-1 py-1 text-right whitespace-nowrap align-top">
                      {r.kiekis == null ? '—' : ltNumber(r.kiekis)} {r.mato_vnt}
                    </td>
                    <td className="px-2 py-1 text-right whitespace-nowrap align-top">
                      {r.suma == null ? '—' : `${ltNumber(r.suma)} €`}
                    </td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Rodoma {shown} iš {ltCount(data.row_count, 'eilutės', 'eilučių', 'eilučių')}
            {data.groups > 0 ? ` · ${ltCount(data.groups, 'grupė', 'grupės', 'grupių')}` : ''}.
            {' '}
            <span className="inline-block w-1 h-2.5 align-middle rounded-sm mr-0.5" style={{ background: 'hsl(var(--conf-med))' }} />
            programos skaičius, patikrinkite
            {' · '}
            <span className="inline-block w-1 h-2.5 align-middle rounded-sm mr-0.5" style={{ background: 'hsl(var(--accent-2))' }} />
            jūsų įvestas ar pataisytas
          </p>
        </>
      )}
    </div>
  );
}
