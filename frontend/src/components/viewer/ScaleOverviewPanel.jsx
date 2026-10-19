/**
 * ScaleOverviewPanel — „Masteliai": every sheet's scale at a glance (Togal-v2 W6, 2026-10-16; research §2).
 *
 * One row per sheet: number, the scale in force, where it comes from, the scale the sheet writes when the
 * dimensions measure another, how many dimension strings were read on it, and its state — nenustatytas ·
 * spėjamas · patvirtintas. A guessed lane scale can be confirmed one sheet at a time or for every sheet that
 * shares it; „Taisyti" sets it by two clicks (the Mastelis tool); „Patikrinti" measures a known length.
 * Rows come from lib/scaleOverview (pure); this file only draws them. ScaleOverviewDock and ScaleGateChip read
 * the visible page from the scroll plugin.
 */
import { useMemo } from 'react';
import { useScroll } from '@embedpdf/plugin-scroll/react';
import { X, Check, Scaling, Ruler, AlertTriangle } from 'lucide-react';
import { buildScaleOverview, overviewCounts, plural } from '@/lib/scaleOverview';
import { SCALE_STATE_LT } from '@/lib/scaleLabel';
import { scaleGateFromScale } from '@/lib/scaleGate';
import { pageScaleIn } from '@/lib/pageScales';
import { visiblePageOf } from '@/lib/visiblePage';

const STATE_CLASS = {
  nenustatytas: 'border-border text-muted-foreground',
  spejamas: 'border-conf-med text-foreground bg-conf-med/[0.12]',
  patvirtintas: 'border-primary text-primary',
};

function StateBadge({ state }) {
  return (
    <span className={`inline-block px-1.5 py-px rounded-[2px] border text-meta leading-tight whitespace-nowrap ${STATE_CLASS[state] || ''}`}>
      {SCALE_STATE_LT[state] || state}
    </span>
  );
}

export function ScaleOverviewPanel({ rows, groups, currentPage, onJump, onConfirm, onFix, onCheck, onClose }) {
  const counts = overviewCounts(rows);
  const btn = 'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] border border-border text-meta text-foreground hover:bg-muted';
  return (
    <div className="w-[380px] max-w-[calc(100vw-24px)] max-h-[70vh] flex flex-col rounded-[2px] border border-border bg-card text-card-foreground shadow-lg" data-testid="scale-overview">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
        <span className="text-ui font-semibold flex-1">Masteliai</span>
        <span className="text-meta text-muted-foreground">
          {counts.patvirtintas} patvirtinti · {counts.spejamas} spėjami · {counts.nenustatytas} nenustatyti
        </span>
        <button type="button" className="p-1 rounded-[2px] hover:bg-muted" onClick={onClose} title="Uždaryti" aria-label="Uždaryti mastelius"><X className="w-4 h-4" /></button>
      </div>
      <p className="px-3 py-1.5 text-meta text-muted-foreground leading-snug border-b border-border">
        Spėjamą mastelį programa nustatė pati — pagal plane užrašytus matmenis arba patalpų plotus. Patikrinkite jį žinomu matmeniu ir patvirtinkite.
      </p>
      {groups.map((g) => (
        <div key={g.ratio} className="px-3 py-1.5 border-b border-border bg-muted/40 text-meta">
          <div>{g.pages.length} {plural(g.pages.length, 'lapas', 'lapai', 'lapų')} su tuo pačiu spėjamu masteliu <b className="mono">{g.label}</b>: {g.pages.join(', ')}</div>
          <button type="button" className={`${btn} mt-1`} onClick={() => onConfirm(g.pages)} data-testid="scale-confirm-all">
            <Check className="w-3.5 h-3.5" />Patvirtinti visus su tuo pačiu masteliu
          </button>
        </div>
      ))}
      <div className="flex-1 overflow-y-auto text-meta">
        {rows.map((r) => (
          <div
            key={r.page}
            className={`px-3 py-2 border-b border-border/60 ${r.page === currentPage ? 'bg-muted/50' : ''}`}
            data-scale-row={r.page}
            data-scale-state={r.state}
          >
            <div className="flex items-center gap-2">
              <button type="button" className="mono tabular text-meta text-muted-foreground hover:underline w-12 text-left shrink-0" onClick={() => onJump(r.page)} title={`Pereiti į ${r.page} lapą`}>
                Lapas {r.page}
              </button>
              <button type="button" className="mono tabular font-semibold w-16 text-left shrink-0 hover:underline" onClick={() => onJump(r.page)}>
                {r.label || '—'}
              </button>
              <StateBadge state={r.state} />
            </div>
            <div className="mt-0.5 text-meta text-muted-foreground leading-snug">
              {r.source}
              {r.strings > 0 && (
                <> · plane perskaityta {r.strings} {plural(r.strings, 'matmuo', 'matmenys', 'matmenų')}{r.sample.length ? ` (${r.sample.join(', ')}${r.strings > r.sample.length ? '…' : ''})` : ''}</>
              )}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-1">
              {r.canConfirm && (
                <button type="button" className={btn} onClick={() => onConfirm([r.page])} title="Patvirtinti, kad šis mastelis teisingas — jis taps jūsų" data-testid="scale-confirm">
                  <Check className="w-3.5 h-3.5" />Patvirtinti
                </button>
              )}
              {r.state !== 'nenustatytas' && (
                <button type="button" className={btn} onClick={() => onCheck(r.page)} title="Spustelėkite du taškus — pamatysite ilgį pagal šį mastelį ir artimiausius plane užrašytus matmenis">
                  <Ruler className="w-3.5 h-3.5" />Patikrinti
                </button>
              )}
              <button type="button" className={btn} onClick={() => onFix(r.page)} title="Nustatyti mastelį patiems: pažymėkite atkarpą, kurios tikrą ilgį žinote">
                <Scaling className="w-3.5 h-3.5" />{r.state === 'nenustatytas' ? 'Nustatyti' : 'Taisyti'}
              </button>
            </div>
            {r.stale && (
              <div className="mt-1 text-meta text-foreground flex items-start gap-1">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
                Patvirtinote 1:{r.stale.confirmed}, bet perskaičius brėžinį iš naujo matmenys rodo 1:{r.stale.now}. Patikrinkite.
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/** The panel, connected to the viewer's scroll state (jump + highlight the visible sheet). */
export function ScaleOverviewDock({ documentId, project, totalPages, durable, onConfirm, onFix, onCheck, onClose }) {
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const currentPage = visiblePageOf(scroll);
  const { rows, groups } = useMemo(
    () => buildScaleOverview(project, { pageCount: totalPages, durable }),
    [project, totalPages, durable],
  );
  const jump = (page) => scrollApi?.scrollToPage({ pageNumber: page, behavior: 'smooth' });
  return (
    <ScaleOverviewPanel
      rows={rows}
      groups={groups}
      currentPage={currentPage}
      onJump={jump}
      onConfirm={onConfirm}
      onFix={(page) => { jump(page); onFix(page); }}
      onCheck={(page) => { jump(page); onCheck(page); }}
      onClose={onClose}
    />
  );
}

/**
 * The soft gate (lib/scaleGate): while a length or area tool is armed on a sheet with no scale, say so — the
 * tool still works. Counting needs no scale, so the count tool shows nothing.
 */
export function ScaleGateChip({ documentId, scales, tool, onSetScale }) {
  const { state: scroll } = useScroll(documentId);
  const page = visiblePageOf(scroll);
  if (!['distance', 'area', 'perimeter'].includes(tool)) return null;
  const gate = scaleGateFromScale(pageScaleIn(scales, page));
  if (gate.ok) return null;
  return (
    <div className="absolute top-11 left-1/2 -translate-x-1/2 z-30 px-3 py-1 rounded-full border border-border bg-card text-meta text-foreground shadow-md flex items-center gap-2 whitespace-nowrap" data-testid="scale-gate-chip">
      <AlertTriangle className="w-3.5 h-3.5" />
      {gate.reason}
      {onSetScale && (
        <button type="button" className="underline hover:no-underline" onClick={onSetScale}>Nustatyti</button>
      )}
    </div>
  );
}
