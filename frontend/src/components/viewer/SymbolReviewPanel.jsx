import { useCallback, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { X, Loader2, AlertTriangle, Layers } from 'lucide-react';
import { useScroll } from '@embedpdf/plugin-scroll/react';
import { findSymbol, recordDecision } from '@/lib/cvToolsApi';
import { makeCountType } from '@/lib/measurements';
import {
  normalizeCandidates, visibleCandidates, countLabel, groupByPage, countsByPage, unusualPages,
  planAllPages, pageRanges, candidatesToMeasurements, klassFor, decisionsToRecord, rejectionsToRecord, formatScore,
  DEFAULT_THRESHOLD, MIN_THRESHOLD, MAX_RUN_MS, MAX_PAGES_PER_RUN, UNUSUAL_WARNING, SYMBOL_SOURCE,
} from '@/lib/symbolSearch';

// What the status bar and the pill above the drawing say, per step.
export const SYMBOL_HINTS = {
  box: 'Rasti panašius: 1) tempdami apveskite vieną simbolį kuo glaudžiau 2) peržiūrėkite rastus 3) „Pridėti kaip kiekį" · Esc — atšaukti',
  searching: 'Rasti panašius: ieškoma panašių simbolių… · Esc — atšaukti',
  review: 'Peržiūra: spustelėkite neteisingą žymę arba ✕ — pašalinti · slankiklis — riba · „Pridėti kaip kiekį" · naujas rėmelis — nauja paieška · Esc — atšaukti',
};

/**
 * useSymbolSearch — the state of one „Rasti panašius" session. Lives in
 * TakeoffViewer (page hosts unmount on scroll). Pure rules are in
 * lib/symbolSearch; this hook only sequences the backend calls.
 */
export function useSymbolSearch({ projectId, countTypes, onAdd }) {
  const [active, setActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [template, setTemplate] = useState(null);     // {page, box}
  const [byPage, setByPage] = useState({});           // {[page]: {candidates, truncated}}
  const [removed, setRemoved] = useState(() => new Set());
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [hoveredId, setHoveredId] = useState(null);
  const [progress, setProgress] = useState(null);     // {done, total, page}
  const [skipped, setSkipped] = useState(null);       // {pages: [], why}
  const [error, setError] = useState(null);
  // the type the found marks join (W5-A A8: „Rasti panašius" from a mark — its own type, so its row link carries over)
  const [preferredTypeId, setPreferredTypeId] = useState(null);
  const runRef = useRef(0);

  const reset = () => {
    runRef.current += 1;
    setBusy(false); setTemplate(null); setByPage({}); setRemoved(new Set());
    setHoveredId(null); setProgress(null); setSkipped(null); setError(null);
  };
  const open = () => { reset(); setThreshold(DEFAULT_THRESHOLD); setPreferredTypeId(null); setActive(true); };
  const finish = () => { reset(); setActive(false); setPreferredTypeId(null); };

  const all = useMemo(() => Object.values(byPage).flatMap((r) => r.candidates), [byPage]);
  const found = useMemo(() => all.filter((c) => !removed.has(c.id)).length, [all, removed]);
  const visible = useMemo(() => visibleCandidates(all, threshold, removed), [all, threshold, removed]);
  const groups = useMemo(() => groupByPage(visible), [visible]);
  const numbers = useMemo(() => {
    const out = {};
    let n = 1;
    for (const g of groups) for (const c of g.items) out[c.id] = n++;
    return out;
  }, [groups]);
  const pageCounts = useMemo(() => {
    const counts = countsByPage(visible);
    for (const p of Object.keys(byPage)) if (!(p in counts)) counts[p] = 0;
    return counts;
  }, [visible, byPage]);
  const unusual = useMemo(() => unusualPages(pageCounts), [pageCounts]);
  const truncatedPages = Object.entries(byPage).filter(([, r]) => r.truncated).map(([p]) => Number(p));
  const rasterPages = Object.entries(byPage).filter(([, r]) => r.warning).map(([p]) => Number(p));
  const phase = !active ? null : busy ? 'searching' : (template ? 'review' : 'box');

  const searchPage = async (page, tpl) => {
    const out = await findSymbol({
      projectId, pageIdx: page - 1, templatePageIdx: tpl.page - 1, boxPt: tpl.box, minScore: MIN_THRESHOLD,
    });
    return {
      candidates: normalizeCandidates(page, out.candidates || []),
      truncated: !!out.truncated,
      // Raster / dark sheet: the backend did not search it and says why.
      warning: out.warning_lt || null,
    };
  };

  const runBox = async (page, box, { force = false } = {}) => {
    if (busy && !force) return;
    if (!box) { toast.info('Rėmelis per mažas — tempdami apveskite visą simbolį'); return; }
    const run = ++runRef.current;
    const tpl = { page, box };
    setTemplate(tpl); setByPage({}); setRemoved(new Set()); setSkipped(null); setError(null);
    setBusy(true); setProgress({ done: 0, total: 1, page });
    try {
      const res = await searchPage(page, tpl);
      if (run !== runRef.current) return;
      setByPage({ [page]: res });
    } catch (e) {
      if (run !== runRef.current) return;
      setError(e?.message || 'Paieška nepavyko');
      setTemplate(null);
    } finally {
      if (run === runRef.current) { setBusy(false); setProgress(null); }
    }
  };

  const searchAllPages = async (totalPages) => {
    if (!template || busy || !totalPages) return;
    const run = ++runRef.current;
    const tpl = template;
    const { pages, skipped: capped } = planAllPages(totalPages, tpl.page, {
      maxPages: MAX_PAGES_PER_RUN, alreadyDone: Object.keys(byPage).map(Number),
    });
    setBusy(true); setError(null); setSkipped(null);
    const started = Date.now();
    const failed = [];
    let i = 0;
    for (; i < pages.length; i += 1) {
      if (run !== runRef.current) return;
      if (Date.now() - started > MAX_RUN_MS) break;
      const page = pages[i];
      setProgress({ done: i, total: pages.length, page });
      try {
        const res = await searchPage(page, tpl);
        if (run !== runRef.current) return;
        setByPage((prev) => ({ ...prev, [page]: res }));
      } catch {
        failed.push(page);
      }
    }
    if (run !== runRef.current) return;
    const timedOut = pages.slice(i);
    const notSearched = [...capped, ...timedOut];
    if (notSearched.length || failed.length) {
      setSkipped({
        pages: notSearched,
        failed,
        why: timedOut.length ? `laiko riba ${Math.round(MAX_RUN_MS / 1000)} s` : `riba ${MAX_PAGES_PER_RUN} lapų per kartą`,
      });
    }
    setBusy(false); setProgress(null);
  };

  const stop = () => {
    runRef.current += 1;
    setBusy(false); setProgress(null);
    setSkipped((s) => s || { pages: [], failed: [], why: 'sustabdyta' });
  };

  const remove = (id) => {
    setRemoved((prev) => { const n = new Set(prev); n.add(id); return n; });
    setHoveredId((h) => (h === id ? null : h));
  };

  const sendDecisions = useCallback((list, klass) => {
    if (!list.length) return 0;
    let failures = 0;
    // Sequential, fire-and-forget: the corpus must not slow the person down.
    (async () => {
      for (const { c, decision } of list) {
        try {
          await recordDecision({
            project_id: projectId, page_idx: c.page - 1, box_pt: c.box,
            klass, decision, confidence: c.score, source: SYMBOL_SOURCE,
          });
        } catch { failures += 1; }
      }
      if (failures) {
        toast.warning(`Mokymo duomenų įrašyti nepavyko (${failures} iš ${list.length})`);
      }
    })();
    return list.length;
  }, [projectId]);

  const recordAll = (type) => sendDecisions(decisionsToRecord(all, threshold, removed), klassFor(type));

  // Cancel (Esc, ✕, another tool): nothing is counted, but what the person removed
  // by hand was a judgement — keep it as rejects, under the class of the type the
  // review panel had chosen (its close button passes it) or the neutral 'simbolis' (Esc, another tool).
  const close = (klassType = null) => {
    sendDecisions(rejectionsToRecord(all, removed), klassFor(klassType));
    finish();
  };

  // typeId of an existing type, or newLabel for a new one.
  const add = ({ typeId, newLabel }) => {
    if (!visible.length) return false;
    let type = countTypes.find((t) => t.id === typeId) || null;
    let created = null;
    if (!type) {
      const label = String(newLabel || '').trim();
      if (!label) { toast.info('Įrašykite naujo tipo pavadinimą, pvz. „Durys"'); return false; }
      created = makeCountType(label, countTypes);
      type = created;
    }
    const marks = candidatesToMeasurements(visible, type);
    onAdd?.(marks, created);
    recordAll(type);
    finish();
    toast.success(`Pridėta ${marks.length} vnt. „${type.label}"`, {
      description: 'Rasta automatiškai — tuščiavidurės žymės brėžinyje; patikrinkite kiekvieną. Sąraše „Matavimai" jos pažymėtos geltonai.',
    });
    return true;
  };

  // „Rasti panašius" from a mark (W5-A A8): the session opens with the template box already drawn round it and
  // the mark's type chosen — the search runs at once, he reviews and adds.
  const openWith = ({ page, box, typeId = null }) => {
    reset();
    setThreshold(DEFAULT_THRESHOLD);
    setPreferredTypeId(typeId);
    setActive(true);
    runBox(page, box, { force: true });
  };

  return {
    active, phase, open, openWith, preferredTypeId, close, template, threshold, setThreshold, hoveredId, setHoveredId,
    all, visible, groups, numbers, found, pageCounts, unusual, truncatedPages, rasterPages,
    progress, skipped, error, runBox, searchAllPages, stop, remove, add,
    searchedPages: Object.keys(byPage).map(Number).sort((a, b) => a - b),
  };
}

/**
 * SymbolReviewPanel — the floating review list of a „Rasti panašius" session:
 * live count with the slider, candidates per sheet with a score bar and ✕,
 * the honesty warning, „Ieškoti visuose lapuose" with a progress pill and
 * „Pridėti kaip kiekį" into a chosen or new count type.
 */
export default function SymbolReviewPanel({ documentId, search, countTypes = [], totalPages = 1 }) {
  const { provides: scrollApi } = useScroll(documentId);
  const [typeChoice, setTypeChoice] = useState(() => (search?.preferredTypeId && countTypes.some((t) => t.id === search.preferredTypeId)
    ? search.preferredTypeId : (countTypes[0]?.id ?? '__new')));
  const [newLabel, setNewLabel] = useState('');
  const [checkedUnusual, setCheckedUnusual] = useState(false);
  const s = search;
  const unusualList = Object.keys(s.unusual).map(Number);
  const hasUnusual = unusualList.length > 0;
  const canAdd = s.visible.length > 0 && s.phase === 'review' && (!hasUnusual || checkedUnusual);
  const onlyOneSheet = s.searchedPages.length <= 1;

  return (
    <div className="flex flex-col p-2 rounded-lg border bg-card text-card-foreground shadow-lg" data-testid="symbol-review-panel">
      <div className="flex items-center px-1 pb-1">
        <h3 className="text-xs font-semibold text-muted-foreground flex-1"
          title="Apveskite vieną simbolį — programa suras panašius pagal formą. Tai pagalba skaičiuoti, ne tikras atpažinimas: patikrinkite kiekvieną.">
          Rasti panašius
        </h3>
        <button type="button" onClick={() => s.close(countTypes.find((t) => t.id === typeChoice) || null)} title="Uždaryti paiešką (Esc) — niekas nepridedama"
          className="p-0.5 rounded text-muted-foreground hover:bg-accent hover:text-accent-foreground" aria-label="Uždaryti">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {s.phase === 'box' && !s.error && (
        <p className="px-1 text-xs text-muted-foreground leading-snug">
          Tempdami apveskite <b>vieną</b> simbolį brėžinyje (pvz., durų varstymo lanką) <b>kuo glaudžiau</b> — į rėmelį patekusios sienos ar užrašai laikomi simbolio dalimi ir panašių randama mažiau. Programa ieškos panašių pagal formą šiame lape.
        </p>
      )}
      {s.error && (
        <p className="px-1 text-xs text-conf-low leading-snug" role="alert">{s.error} — apveskite simbolį dar kartą.</p>
      )}

      {s.progress && (
        <div className="mx-1 my-1 inline-flex items-center gap-1.5 self-start px-2 py-0.5 rounded-full bg-muted text-meta text-foreground" data-testid="symbol-progress">
          <Loader2 className="w-3 h-3 animate-spin" />
          {s.progress.total > 1
            ? `Ieškoma: ${s.progress.page} lapas (${s.progress.done + 1} iš ${s.progress.total})`
            : `Ieškoma ${s.progress.page} lape…`}
          {s.progress.total > 1 && (
            <button type="button" className="ml-1 underline" onClick={s.stop}>Sustabdyti</button>
          )}
        </div>
      )}

      {s.template && (
        <>
          <div className="px-1 pt-1 flex items-baseline gap-2">
            <span className="text-sm font-medium tabular-nums" data-testid="symbol-count-label">
              {countLabel({ found: s.found, shown: s.visible.length, threshold: s.threshold })}
            </span>
          </div>
          <label className="px-1 py-1 flex items-center gap-2 text-meta text-muted-foreground"
            title="Panašumas pagal formą (0–1), ne tikimybė. Didinkite — mažiau, bet tikresnių; mažinkite — daugiau, bet daugiau klaidų.">
            <span className="whitespace-nowrap">Riba</span>
            <input type="range" min={MIN_THRESHOLD} max={1} step={0.01} value={s.threshold}
              onChange={(e) => s.setThreshold(Number(e.target.value))}
              className="flex-1 accent-viewer-chrome-active" aria-label="Panašumo riba" data-testid="symbol-threshold" />
            <span className="mono tabular w-8 text-right text-foreground">{formatScore(s.threshold)}</span>
          </label>

          {hasUnusual && (
            <div className="mx-1 my-1 p-2 rounded border border-conf-med/50 bg-conf-med/[0.08] text-meta leading-snug" data-testid="symbol-unusual">
              <div className="flex gap-1.5"><AlertTriangle className="w-3.5 h-3.5 shrink-0 text-conf-med" />
                <span>{UNUSUAL_WARNING} (lap. {pageRanges(unusualList)}).</span></div>
              <label className="mt-1.5 flex items-center gap-1.5">
                <input type="checkbox" checked={checkedUnusual} onChange={(e) => setCheckedUnusual(e.target.checked)} />
                Peržiūrėjau — pridėti vis tiek
              </label>
            </div>
          )}
          {s.rasterPages.length > 0 && (
            <p className="mx-1 my-1 px-2 py-1 rounded bg-muted text-meta leading-snug" data-testid="symbol-raster">
              Lap. {pageRanges(s.rasterPages)}: lapas rastrinis arba tamsus — panašumų paieška nepatikima, ten neieškota.
            </p>
          )}
          {s.truncatedPages.length > 0 && (
            <p className="px-1 text-meta text-muted-foreground">Lap. {pageRanges(s.truncatedPages)} rodomi tik 300 panašiausių.</p>
          )}

          <div className="mt-1 max-h-[34vh] overflow-y-auto border-y border-border/60" data-testid="symbol-list">
            {s.groups.length === 0 && !s.progress && (
              <p className="px-2 py-2 text-xs text-muted-foreground">Virš ribos nieko nerasta — sumažinkite ribą arba apveskite kitą pavyzdį.</p>
            )}
            {s.groups.map((g) => (
              <div key={g.page}>
                <div className="sticky top-0 bg-card px-2 py-1 text-meta font-medium text-muted-foreground flex items-center">
                  <button type="button" className="hover:underline" onClick={() => scrollApi?.scrollToPage({ pageNumber: g.page, behavior: 'smooth' })}
                    title={`Rodyti ${g.page} lapą`}>{g.page} lapas</button>
                  <span className="ml-auto tabular-nums">{g.items.length} vnt.</span>
                  {s.unusual[g.page] && <AlertTriangle className="ml-1 w-3 h-3 text-conf-med" aria-label="Neįprastai daug" />}
                </div>
                {g.items.map((c) => (
                  <div key={c.id}
                    className={`flex items-center gap-2 px-2 py-0.5 text-xs ${s.hoveredId === c.id ? 'bg-ov-proposed/[0.12]' : ''}`}
                    onMouseEnter={() => s.setHoveredId(c.id)} onMouseLeave={() => s.setHoveredId(null)}
                    data-testid="symbol-row">
                    <button type="button" className="mono tabular w-6 text-right text-muted-foreground hover:underline"
                      onClick={() => scrollApi?.scrollToPage({ pageNumber: c.page, behavior: 'smooth' })} title="Rodyti lape">
                      {s.numbers[c.id]}
                    </button>
                    <span className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden" title={`Panašumas ${formatScore(c.score)}`}>
                      <span className="block h-full rounded-full"
                        style={{ width: `${Math.round(Math.max(0, (c.score - MIN_THRESHOLD) / (1 - MIN_THRESHOLD)) * 100)}%`,
                          background: c.isSource ? 'hsl(var(--ov-read))' : 'hsl(var(--ov-proposed))' }} />
                    </span>
                    <span className="mono tabular w-8 text-right">{formatScore(c.score)}</span>
                    {c.isSource && <span className="text-meta text-muted-foreground" title="Tai jūsų apvestas pavyzdys">pavyzdys</span>}
                    <button type="button" onClick={() => s.remove(c.id)} aria-label={`Pašalinti ${s.numbers[c.id]}`}
                      title="Ne tas simbolis — pašalinti" data-testid="symbol-remove"
                      className="p-0.5 rounded text-muted-foreground hover:bg-conf-low hover:text-white">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            ))}
          </div>

          {s.skipped && (
            <p className="px-1 pt-1 text-meta text-muted-foreground leading-snug" data-testid="symbol-skipped">
              {s.skipped.pages.length > 0 && `Neieškota lap. ${pageRanges(s.skipped.pages)} (${s.skipped.why}). `}
              {s.skipped.failed?.length > 0 && `Nepavyko lap. ${pageRanges(s.skipped.failed)}. `}
              {s.skipped.pages.length === 0 && !s.skipped.failed?.length && `Paieška ${s.skipped.why}.`}
            </p>
          )}

          <div className="pt-1.5 flex flex-col gap-1.5">
            {totalPages > 1 && (
              <button type="button" disabled={!!s.progress || s.searchedPages.length >= totalPages}
                onClick={() => s.searchAllPages(totalPages)}
                className="inline-flex items-center justify-center gap-1.5 px-2 py-1 rounded border border-border text-xs hover:bg-accent disabled:opacity-50"
                title={`Ieškoti to paties simbolio kituose lapuose (iki ${MAX_PAGES_PER_RUN} lapų, ~3 s lapui)`}
                data-testid="symbol-all-pages">
                <Layers className="w-3.5 h-3.5" />
                {onlyOneSheet ? 'Ieškoti visuose lapuose'
                  : s.searchedPages.length >= totalPages ? `Ieškota visuose ${totalPages} lapuose`
                    : `Ieškota ${s.searchedPages.length} iš ${totalPages} lapų — ieškoti likusiuose`}
              </button>
            )}
            <div className="flex items-center gap-1.5">
              <select value={typeChoice} onChange={(e) => setTypeChoice(e.target.value)}
                className="flex-1 min-w-0 h-7 px-1 rounded border border-border bg-background text-xs" aria-label="Kiekio tipas" data-testid="symbol-type">
                {countTypes.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
                <option value="__new">+ Naujas tipas…</option>
              </select>
            </div>
            {typeChoice === '__new' && (
              <input type="text" value={newLabel} onChange={(e) => setNewLabel(e.target.value)}
                placeholder="Tipo pavadinimas, pvz. Durys"
                className="h-7 px-2 rounded border border-border bg-background text-xs" aria-label="Naujo tipo pavadinimas"
                data-testid="symbol-new-type"
                onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); e.currentTarget.blur(); } }} />
            )}
            <button type="button" disabled={!canAdd}
              onClick={() => s.add({ typeId: typeChoice === '__new' ? null : typeChoice, newLabel })}
              className="px-2 py-1.5 rounded bg-viewer-chrome-active text-white text-xs font-medium disabled:opacity-50"
              title={hasUnusual && !checkedUnusual
                ? 'Pirmiausia peržiūrėkite įspėjimą viršuje'
                : 'Rodomos žymės taps kiekio žymėmis (geltonos — rastos automatiškai, patikrinkite)'}
              data-testid="symbol-add">
              Pridėti kaip kiekį ({s.visible.length} vnt.)
            </button>
          </div>
        </>
      )}
    </div>
  );
}
