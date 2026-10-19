/**
 * LegendReviewPanel — the row-by-row review of „Pažymėti legendą" (Pathon v3 W2-B, B2).
 *
 * Shown in the workspace's right panel (TakeoffViewer portals it there; a viewer without that host shows it
 * floating beside the drawing). Each legend row: its glyph cut from the drawing, its text, how many marks
 * were found on which sheet with the counter's own sentence, a few examples; ✔ keep · 🗑 drop · „Kitas
 * pavadinimas". A material or line sample says why it is not counted and offers a measurement instead.
 * ONE „Sukurti kiekius (N)" at the bottom — nothing exists before it.
 */
import { useState } from 'react';
import { Check, Loader2, PenLine, Ruler, Trash2, Undo2, X } from 'lucide-react';
import { useScroll } from '@embedpdf/plugin-scroll/react';
import { API_BASE } from '@/lib/apiBase';
import Notice from '@/components/ui/Notice';
import { createLabel, keptInstances, perPage, perPageText, rowName } from '@/lib/legendReview';

const BTN = 'inline-flex min-h-[36px] items-center gap-1.5 rounded-[2px] border px-2.5 text-[14px] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50';
const PLAIN = `${BTN} border-border bg-card hover:bg-muted`;
const ON = `${BTN} border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2)/0.1)] text-[hsl(var(--accent-2))]`;

const crop = (url) => (url ? `${API_BASE}${url}` : null);

function exampleUrl(projectId, inst) {
  const b = inst.box_pct;
  if (!projectId || !Array.isArray(b)) return null;
  const pad = 0.012;
  const r = [Math.max(0, b[0] - pad), Math.max(0, b[1] - pad), Math.min(1, b[2] + pad), Math.min(1, b[3] + pad)]
    .map((v) => v.toFixed(4)).join(',');
  return `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/evidence?page=${inst.page}&rect=${r}&dpi=110`;
}

function Row({ row, count, review, removed, projectId, legend, onPage, onMeasure }) {
  const [naming, setNaming] = useState(false);
  const [draft, setDraft] = useState('');
  const keep = !!review?.keep;
  const sample = row.countable === false;
  const kept = keptInstances(count, removed);
  const removedHere = (count?.instances?.length || 0) - kept.length;
  const name = rowName(row, review);
  const examples = kept.slice(0, 3);
  const hot = legend.hoveredRowId === row.row_id;

  return (
    <li
      className={`border-t border-border px-3 py-3 first:border-t-0 ${hot ? 'bg-muted/60' : ''}`}
      onMouseEnter={() => legend.setHoveredRow(row.row_id)}
      onMouseLeave={() => legend.setHoveredRow(null)}
      data-testid="legend-row"
      data-row-id={row.row_id}
      data-keep={keep ? '1' : '0'}
    >
      <div className="flex items-start gap-3">
        {crop(row.glyph_crop_url) && (
          <img src={crop(row.glyph_crop_url)} alt={`Ženklas: ${row.text || ''}`} className="h-14 w-14 shrink-0 rounded-[2px] border border-border bg-white object-cover" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold leading-snug text-foreground">
            {name}
            {review?.name ? <span className="block text-[14px] font-normal text-muted-foreground">legendoje: {row.text}</span> : null}
          </p>
          {!sample && (
            <p className="mt-0.5 font-mono text-[14px] tabular-nums text-foreground" data-testid="legend-row-count">
              {kept.length} vnt. · {perPageText(perPage(kept))}
            </p>
          )}
          <p className="mt-1 text-[14px] leading-snug text-[hsl(var(--ink-2))]">{count?.sentence_lt || row.reason_lt || ''}</p>
        </div>
      </div>

      {examples.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Pavyzdžiai brėžinyje">
          {examples.map((inst) => (
            <button
              key={inst.id}
              type="button"
              onClick={() => onPage(inst.page)}
              onMouseEnter={() => legend.setHovered(inst.id)}
              onMouseLeave={() => legend.setHovered(null)}
              title={`Lapas ${inst.page} — rodyti brėžinyje`}
              className="rounded-[2px] border border-border bg-white p-0.5 hover:border-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <img src={exampleUrl(projectId, inst)} alt={`Rastas ženklas, lapas ${inst.page}`} className="h-14 w-14 object-cover" loading="lazy" />
            </button>
          ))}
          {kept.length > examples.length && <span className="self-center text-[14px] text-muted-foreground">+{kept.length - examples.length} brėžinyje</span>}
        </div>
      )}

      {sample ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          <button type="button" className={PLAIN} onClick={() => onMeasure('area')} data-testid="legend-measure-area">
            <Ruler className="h-4 w-4" aria-hidden="true" /> Matuoti plotą
          </button>
          <button type="button" className={PLAIN} onClick={() => onMeasure('perimeter')}>
            <Ruler className="h-4 w-4" aria-hidden="true" /> Matuoti ilgį
          </button>
        </div>
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <button type="button" className={keep ? ON : PLAIN} aria-pressed={keep} onClick={() => legend.setKeep(row.row_id, true)} data-testid="legend-keep">
            <Check className="h-4 w-4" aria-hidden="true" /> Tinka
          </button>
          <button type="button" className={!keep ? ON : PLAIN} aria-pressed={!keep} onClick={() => legend.setKeep(row.row_id, false)} data-testid="legend-drop">
            <Trash2 className="h-4 w-4" aria-hidden="true" /> Nereikia
          </button>
          <button type="button" className={PLAIN} onClick={() => { setDraft(review?.name || row.text || ''); setNaming((v) => !v); }} data-testid="legend-rename">
            <PenLine className="h-4 w-4" aria-hidden="true" /> Kitas pavadinimas
          </button>
          {removedHere > 0 && (
            <button type="button" className={PLAIN} onClick={() => legend.restoreRow(row.row_id)} title="Grąžinti žymes, kurias pašalinote brėžinyje">
              <Undo2 className="h-4 w-4" aria-hidden="true" /> Grąžinti {removedHere}
            </button>
          )}
        </div>
      )}

      {naming && !sample && (
        <form
          className="mt-2 flex gap-1.5"
          onSubmit={(e) => { e.preventDefault(); legend.rename(row.row_id, draft.trim() || null); legend.setKeep(row.row_id, true); setNaming(false); }}
        >
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); setNaming(false); } }}
            aria-label="Kiekio pavadinimas"
            className="h-9 min-w-0 flex-1 rounded-[2px] border border-border bg-background px-2 text-[14px]"
            data-testid="legend-rename-input"
          />
          <button type="submit" className={PLAIN}>Išsaugoti</button>
        </form>
      )}
    </li>
  );
}

export default function LegendReviewPanel({ documentId, projectId, legend, onMeasure }) {
  const { provides: scrollApi } = useScroll(documentId);
  const toPage = (page) => scrollApi?.scrollToPage({ pageNumber: page, behavior: 'smooth' });
  const busy = legend.phase === 'suggesting' || legend.phase === 'reading' || legend.phase === 'counting' || legend.phase === 'creating';
  const marks = legend.toCreate.reduce((n, r) => n + keptInstances(legend.counts[r.row_id], legend.removed).length, 0);
  const n = legend.toCreate.length;

  return (
    <section className="flex h-full min-h-0 flex-col bg-card text-card-foreground" aria-label="Legendos peržiūra" data-testid="legend-review-panel">
      <header className="flex items-center gap-2 border-b border-border px-3 py-2.5">
        <h2 className="flex-1 text-[16px] font-semibold">Pažymėti legendą</h2>
        <button type="button" onClick={legend.close} className={PLAIN} aria-label="Uždaryti legendą (Esc) — niekas nesukuriama" title="Uždaryti (Esc) — niekas nesukuriama">
          <X className="h-4 w-4" aria-hidden="true" /> Uždaryti
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {legend.phase === 'proposed' && (
          <p className="px-3 py-3 text-[14px] leading-snug text-[hsl(var(--ink-2))]">
            Brėžinyje brūkšniniu rėmeliu pažymėjau, kur, mano manymu, yra legenda. Jei tai ji — spauskite „Taip“ apačioje
            arba spustelėkite rėmelį; jei ne — tempdami apveskite tikrąją.
          </p>
        )}
        {legend.phase === 'box' && (
          <p className="px-3 py-3 text-[14px] leading-snug text-[hsl(var(--ink-2))]">
            {legend.notice ? `${legend.notice}. ` : ''}Tempdami apveskite legendą brėžinyje — ženklus kartu su jų pavadinimais.
          </p>
        )}
        {busy && (
          <p className="flex items-center gap-2 px-3 py-3 text-[14px] text-muted-foreground" data-testid="legend-busy">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            {legend.phase === 'suggesting' ? 'Ieškoma legendos šiame lape…'
              : legend.phase === 'reading' ? 'Skaitomos legendos eilutės…'
                : legend.phase === 'counting' ? 'Skaičiuojami ženklai visuose lapuose — gali užtrukti iki minutės…'
                  : 'Kuriami kiekiai…'}
          </p>
        )}

        {legend.phase === 'review' && legend.reuse && !legend.reuse.applied && (
          <Notice
            className="mx-3 mt-3"
            title="Rasta ankstesnio projekto legenda — pritaikyti?"
            action={(
              <span className="flex gap-1.5">
                <button type="button" className={PLAIN} onClick={legend.applyReuse} data-testid="legend-reuse-apply">Pritaikyti</button>
                <button type="button" className={PLAIN} onClick={legend.dismissReuse}>Ne</button>
              </span>
            )}
          >
            {legend.reuse.matched} iš {legend.reuse.total} eilučių sutampa
            {legend.reuse.architect ? ` su projektuotojo „${legend.reuse.architect}“ legenda` : ' su anksčiau šiame projekte pažymėta legenda'}.
            Pritaikius grįš jūsų tada duoti pavadinimai ir pasirinkimai.
          </Notice>
        )}
        {legend.phase === 'review' && legend.reuse?.applied && (
          <p className="mx-3 mt-3 text-[14px] text-[hsl(var(--ink-2))]">Pritaikyta ankstesnė legenda — patikrinkite eilutes.</p>
        )}

        {(legend.phase === 'review' || legend.phase === 'creating') && (
          <>
            <ul className="mt-2" data-testid="legend-rows">
              {legend.rows.map((row) => (
                <Row
                  key={row.row_id}
                  row={row}
                  count={legend.counts[row.row_id]}
                  review={legend.review[row.row_id]}
                  removed={legend.removed}
                  projectId={projectId}
                  legend={legend}
                  onPage={toPage}
                  onMeasure={onMeasure}
                />
              ))}
            </ul>
            <label className="block border-t border-border px-3 py-3 text-[14px]">
              <span className="font-medium">Projektuotojas (nebūtina)</span>
              <input
                value={legend.architect}
                onChange={(e) => legend.setArchitect(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Escape') e.currentTarget.blur(); }}
                placeholder="pvz. studijos pavadinimas"
                className="mt-1 h-9 w-full rounded-[2px] border border-border bg-background px-2 text-[14px]"
                data-testid="legend-architect"
              />
              <span className="mt-1 block text-[14px] leading-snug text-muted-foreground">
                Įrašius, kitame šio projektuotojo projekte programa pasiūlys šią legendą su jūsų pavadinimais.
              </span>
            </label>
          </>
        )}
      </div>

      {(legend.phase === 'review' || legend.phase === 'creating') && (
        <footer className="border-t border-border px-3 py-3">
          <button
            type="button"
            disabled={!n || legend.phase === 'creating'}
            onClick={legend.create}
            className={`${BTN} min-h-[44px] w-full justify-center border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] text-[15px] font-semibold text-white hover:opacity-95`}
            data-testid="legend-create"
          >
            {legend.phase === 'creating' ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Check className="h-4 w-4" aria-hidden="true" />}
            {createLabel(n)}
          </button>
          <p className="mt-1.5 text-[14px] leading-snug text-muted-foreground">
            {n ? `${n} kiek. ir ${marks} žym. brėžinyje — sąmatos eilutės skaičiuosis pačios. Po to galėsite atšaukti.` : 'Pažymėkite bent vieną eilutę „Tinka“.'}
          </p>
        </footer>
      )}
    </section>
  );
}
