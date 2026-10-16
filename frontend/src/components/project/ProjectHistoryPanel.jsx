/**
 * ProjectHistoryPanel — „Istorija": every saved state of the project, newest first (togal-v2 W10).
 *
 * Each row says when and how the state came about (išsaugota, brėžinys perskaitytas, atsakytas klausimas,
 * prieš grąžinant…). „Palyginti su dabartine" prints what changed since that version in his words (the
 * server's sentences, api/version_diff.py); „Grąžinti" asks first, keeps the state it replaces as a
 * version of its own and offers the same one-click „Atšaukti" toast a row delete has.
 *
 * Not the viewer's „Istorija" (components/viewer/HistoryPanel.jsx): that one is the last 50 measurement
 * and count-mark actions, held in this tab's memory only. The drawer says so.
 */
import { useCallback, useEffect, useState } from 'react';
import { History, RotateCcw, X, GitCompare } from 'lucide-react';
import { toast } from 'sonner';

import { useConfirm } from '@/components/ui/confirm-provider';
import { adoptServerProject, flushProjectSaves } from '@/lib/projectStore';
import { closesOnEscape } from '@/lib/escapeToClose';
import {
  diffSections, fetchVersionDiff, fetchVersions, restoreVersion, versionRows,
} from '@/lib/projectVersions';

const btn = 'inline-flex items-center gap-1.5 rounded-[2px] border border-border-strong bg-card text-foreground/85 '
  + 'hover:bg-muted/50 disabled:opacity-40 disabled:hover:bg-card transition-colors';

export default function ProjectHistoryPanel({ project, onClose, onRestored }) {
  const confirm = useConfirm();
  const id = project?.id;
  const [versions, setVersions] = useState(null);     // null = loading
  const [error, setError] = useState(null);
  const [openDiff, setOpenDiff] = useState(null);     // { id, sections | null, error }
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      // a save still on its 400 ms timer belongs in the list too
      await flushProjectSaves();
      setVersions(await fetchVersions(id));
    } catch {
      setError('Nepavyko gauti istorijos. Patikrinkite ryšį ir bandykite dar kartą.');
      setVersions([]);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const onKey = (e) => { if (closesOnEscape(e)) onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const compare = async (row) => {
    if (openDiff?.id === row.id) { setOpenDiff(null); return; }
    setOpenDiff({ id: row.id, sections: null, error: null });
    try {
      await flushProjectSaves();
      const diff = await fetchVersionDiff(id, row.id, 'dabartine');
      setOpenDiff({ id: row.id, sections: diffSections(diff), error: null });
    } catch {
      setOpenDiff({ id: row.id, sections: null, error: 'Nepavyko palyginti. Bandykite dar kartą.' });
    }
  };

  const land = async (versionId) => {
    await flushProjectSaves();
    const saved = await restoreVersion(id, versionId);
    const adopted = adoptServerProject(saved) || saved;
    onRestored?.(adopted);
    return adopted;
  };

  const restore = async (row) => {
    const ok = await confirm({
      title: 'Grąžinti šią versiją?',
      description: `Projektas taps toks, koks buvo ${row.when}. Dabartinė būsena neprarandama: ji lieka `
        + 'istorijoje kaip „Prieš grąžinant“, ir ją galėsite grąžinti atgal.',
      confirmText: 'Grąžinti',
      cancelText: 'Atšaukti',
    });
    if (!ok) return;
    setBusy(true);
    try {
      await land(row.id);
      const list = await fetchVersions(id);
      setVersions(list);
      setOpenDiff(null);
      // the state it replaced is the newest „Prieš grąžinant“ version
      const replaced = list.find((v) => v.saltinis === 'grazinta');
      toast(`Grąžinta versija (${row.when}).`, {
        duration: 8000,
        action: replaced ? {
          label: 'Atšaukti',
          onClick: async () => {
            try {
              await land(replaced.id);
              setVersions(await fetchVersions(id));
              toast.success('Grąžinta būsena prieš grąžinimą.');
            } catch {
              toast.error('Nepavyko atšaukti. Būseną rasite istorijoje kaip „Prieš grąžinant“.');
            }
          },
        } : undefined,
      });
    } catch (e) {
      toast.error(e?.status === 404
        ? 'Šios versijos nebėra — atnaujinkite sąrašą.'
        : 'Nepavyko grąžinti versijos. Projektas nepakeistas.');
    } finally {
      setBusy(false);
    }
  };

  const rows = versionRows(versions);

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0" style={{ background: 'hsl(var(--foreground) / 0.18)' }} onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Projekto istorija"
        data-testid="project-history-panel"
        className="relative h-full overflow-y-auto bg-background border-l border-border shadow-xl w-full sm:w-[520px] p-4 space-y-4"
      >
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-semibold text-foreground flex items-center gap-2" style={{ fontSize: 17 }}>
            <History className="w-4 h-4" aria-hidden /> Projekto istorija
          </h2>
          <button
            type="button" onClick={onClose} title="Uždaryti" aria-label="Uždaryti istoriją"
            className="inline-flex items-center justify-center rounded border border-border-strong bg-card text-foreground/80 hover:bg-muted/50"
            style={{ minHeight: 44, minWidth: 44 }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="rounded-[2px] border border-border bg-card p-3 text-[13px] leading-relaxed text-foreground/85 space-y-1.5">
          <p>
            Čia — kiekviena išsaugota projekto būsena: patalpos, sąmatos eilutės, kainos ir prielaidos.
            Ji laikoma serveryje: paskutinės 30 versijų ir po vieną kiekvienai dienai 90 dienų.
          </p>
          <p className="text-muted-foreground">
            Matavimų ir žymių brėžinyje veiksmus atšaukite brėžinio įrankių juostos mygtuku „Istorija“ —
            jie laikomi tik šiame lange ir dingsta perkrovus puslapį.
          </p>
        </div>

        {error && <p className="text-[13px] text-destructive">{error}</p>}
        {versions === null && <p className="text-[13px] text-muted-foreground">Kraunama…</p>}
        {versions !== null && !rows.length && !error && (
          <p className="text-[13px] text-muted-foreground">
            Versijų dar nėra. Pirmoji atsiras, kai išsaugosite pakeitimą.
          </p>
        )}

        <ol className="space-y-2">
          {rows.map((row) => (
            <li key={row.id} className="rounded-[2px] border border-border bg-card" data-version-id={row.id}>
              <div className="flex items-start gap-3 p-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <span className="mono tabular text-[13px] text-foreground">{row.when}</span>
                    <span className="text-[13px] font-medium text-foreground">{row.sourceText}</span>
                    {row.current && (
                      <span className="text-[10.5px] uppercase tracking-wide rounded-[2px] px-1.5 py-px border border-primary/40 text-primary">
                        dabartinė
                      </span>
                    )}
                  </div>
                  {row.title && <div className="text-[12px] text-muted-foreground mt-0.5">{row.title}</div>}
                </div>
                <div className="flex flex-col gap-1.5 shrink-0">
                  <button
                    type="button" className={btn} style={{ minHeight: 32, padding: '0 10px', fontSize: 12 }}
                    disabled={row.current || busy} onClick={() => compare(row)}
                    aria-expanded={openDiff?.id === row.id}
                  >
                    <GitCompare className="w-3.5 h-3.5" aria-hidden /> Palyginti su dabartine
                  </button>
                  <button
                    type="button" className={btn} style={{ minHeight: 32, padding: '0 10px', fontSize: 12 }}
                    disabled={row.current || busy} onClick={() => restore(row)}
                  >
                    <RotateCcw className="w-3.5 h-3.5" aria-hidden /> Grąžinti
                  </button>
                </div>
              </div>
              {openDiff?.id === row.id && (
                <div className="border-t border-border px-3 py-2.5 text-[13px] space-y-2" data-testid="version-diff">
                  {openDiff.error && <p className="text-destructive">{openDiff.error}</p>}
                  {!openDiff.error && openDiff.sections === null && <p className="text-muted-foreground">Lyginama…</p>}
                  {openDiff.sections && !openDiff.sections.length && (
                    <p className="text-muted-foreground">Ši versija nesiskiria nuo dabartinės patalpomis, eilutėmis ir prielaidomis.</p>
                  )}
                  {openDiff.sections?.length > 0 && (
                    <p className="text-muted-foreground">Kas pasikeitė nuo šios versijos iki dabar (buvo → dabar):</p>
                  )}
                  {openDiff.sections?.map((s) => (
                    <div key={s.key}>
                      <div className="skyrius-header" style={{ fontSize: 10 }}>{s.title}</div>
                      <ul className="mt-1 space-y-0.5">
                        {s.lines.map((line, i) => <li key={i} className="text-foreground/90">{line}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
