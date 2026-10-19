/**
 * SamataTemplateView — the Sąmata step in the contractor's OWN layout.
 *
 * His sections, his order, his row labels (backend `render_samata`). Every row
 * is in one of three states and the sheet never blurs them:
 *
 *   filled     a number we can stand behind (verified or ledgered) — bold;
 *   suggested  our number nobody checked — GREYED, with „Teisinga ✓" and
 *              „Pataisyti"; it is never the value and never exported;
 *   blank      the drawing cannot answer it — an input, „įrašykite".
 *
 * Nothing typed here is stored on the rendered sheet: a typed quantity becomes
 * a hand-added row in `darbu_sarasas` carrying the family key, „Teisinga ✓"
 * stamps the source rows, a price lands on the source row — see
 * `lib/samataTemplate.js`. The view then re-renders from the backend, so what
 * he sees is always what the export will print.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from '@/i18n/react';
import { toast } from 'sonner';
import { Check, Loader2, Pencil } from 'lucide-react';
import { parseLtNumber, isValidAmount } from '@/lib/parseLtNumber';
import { renderSamata, roomsForRender } from '@/lib/samataTemplateApi';
import {
  EXTRA_SECTION, FILL, acceptSuggestion, canTypeQuantity, darbaiFingerprint,
  groupBySection, lineAmount, setPrice, singleSourceRow, summarize, typeQuantity, typedSourceRow,
} from '@/lib/samataTemplate';

const eur = new Intl.NumberFormat('lt-LT', { style: 'currency', currency: 'EUR' });
const qty = new Intl.NumberFormat('lt-LT', { maximumFractionDigits: 2 });

function fmtQty(v) {
  return v == null || v === '' ? '' : qty.format(Number(v));
}

const INPUT = 'h-11 w-24 rounded border border-border bg-background px-2 text-right '
  + 'tabular-nums focus:border-primary outline-none';
const SMALL_BTN = 'inline-flex items-center gap-1 rounded border px-2.5 font-medium '
  + 'transition-colors disabled:opacity-50';

/** One editable number cell: text input with a LT decimal comma, commit on Enter/blur. */
function NumberCell({ value, ariaLabel, placeholder, onCommit, disabled, title }) {
  const { t } = useTranslation();
  const fmt = (v) => (v == null ? '' : String(v).replace('.', ','));
  const [draft, setDraft] = useState(() => fmt(value));
  const [dirty, setDirty] = useState(false);
  // Follow the prop only when IT moves — a committed draft stays on screen
  // until the re-render brings the number back, instead of blinking empty.
  const lastValue = useRef(value);
  useEffect(() => {
    if (lastValue.current !== value) { lastValue.current = value; setDraft(fmt(value)); setDirty(false); }
  }, [value]);

  const commit = () => {
    if (!dirty) return;
    const raw = draft.trim();
    if (raw === '') { setDirty(false); setDraft(fmt(value)); return; }
    const num = parseLtNumber(raw);
    if (!isValidAmount(num)) {
      toast.error(t('project.samataTemplate.badNumber'));
      return;
    }
    setDirty(false);
    if (num !== Number(value ?? NaN)) onCommit(num);
  };

  return (
    <input
      type="text"
      inputMode="decimal"
      value={draft}
      disabled={disabled}
      placeholder={placeholder}
      aria-label={ariaLabel}
      title={title}
      onFocus={(e) => e.target.select()}
      onChange={(e) => { setDraft(e.target.value); setDirty(true); }}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') { e.preventDefault(); commit(); e.currentTarget.blur(); }
        if (e.key === 'Escape') { setDirty(false); setDraft(fmt(value)); e.currentTarget.blur(); }
      }}
      className={INPUT}
      style={{ fontSize: 16 }}
    />
  );
}

function Row({ row, darbai, onDarbaiChange, onOpenLedger }) {
  const { t } = useTranslation();
  const typed = typedSourceRow(row, darbai);
  const typable = canTypeQuantity(row, darbai);
  const priceSource = singleSourceRow(row, darbai);
  const isBlank = row._pildymas === FILL.EMPTY;
  const isSuggested = row._pildymas === FILL.SUGGESTED && row._sablonas;
  const isKita = !row._sablonas;
  const kiekis = row.kiekis;
  const kaina = row.kaina;
  // A merged line may carry its own amount and no single price (lineAmount).
  const suma = lineAmount(row);
  const ownAmount = Boolean(row._suma_be_vieneto_kainos);

  const commitQty = (num) => {
    try {
      onDarbaiChange(typeQuantity(darbai, row, num, { otherLabel: EXTRA_SECTION }));
    } catch {
      toast.error(t('project.samataTemplate.badNumber'));
    }
  };
  const commitPrice = (num) => {
    try { onDarbaiChange(setPrice(darbai, row, num)); } catch { /* not a single-source row */ }
  };
  const accept = () => onDarbaiChange(acceptSuggestion(darbai, row));
  const openSource = () => {
    const src = priceSource || (darbai || []).find((r) => String(r?.id) === String(row._saltinio_id?.[0]));
    if (src && onOpenLedger) onOpenLedger(src);
  };

  return (
    <tr className={`border-b border-border/40 last:border-0 ${isBlank ? 'bg-muted/10' : ''}`}>
      <td className="px-3 py-2 text-sm text-muted-foreground tabular-nums align-top">{row.nr}</td>
      <td className="px-3 py-2 align-top">
        <div className="text-foreground" style={{ fontSize: 16 }}>{row.aprasymas}</div>
        {row._daznumas === 'kartais' && (
          <span
            className="mr-2 text-[12px] uppercase tracking-wide text-muted-foreground"
            title={t('project.samataTemplate.occasionalTitle')}
          >
            {t('project.samataTemplate.occasional')}
          </span>
        )}
        {(isBlank || ownAmount) && row._pastaba && (
          <span className="block text-[13px] text-muted-foreground">{row._pastaba}</span>
        )}
        {typed && (
          <span className="block text-[13px] text-muted-foreground">{t('project.samataTemplate.typed')}</span>
        )}
        {isSuggested && (
          <span className="block text-[13px]" style={{ color: 'hsl(var(--conf-med))' }}>
            {t('project.samataTemplate.suggestedHint')}
          </span>
        )}
      </td>
      <td className="px-3 py-2 text-sm text-muted-foreground align-top">{row.mato_vnt || ''}</td>
      <td className="px-3 py-2 text-right align-top">
        {typable ? (
          <NumberCell
            value={kiekis}
            placeholder={t('project.samataTemplate.typePlaceholder')}
            ariaLabel={t('project.samataTemplate.typeAria', { row: row.aprasymas })}
            onCommit={commitQty}
          />
        ) : isSuggested ? (
          <span
            className="inline-block tabular-nums text-muted-foreground"
            style={{ fontSize: 16, textDecoration: 'none' }}
            title={t('project.samataTemplate.suggestedHint')}
          >
            {fmtQty(row._siulomas_kiekis)}
            <span className="ml-1 text-[12px] uppercase tracking-wide">{t('project.samataTemplate.suggested')}</span>
          </span>
        ) : (
          <span className="font-semibold tabular-nums text-foreground" style={{ fontSize: 16 }}>
            {fmtQty(kiekis)}
          </span>
        )}
      </td>
      <td className="px-3 py-2 text-right align-top">
        {priceSource ? (
          <NumberCell
            value={kaina == null ? null : Number(kaina)}
            placeholder="0,00"
            ariaLabel={t('project.samataTemplate.priceAria', { row: row.aprasymas })}
            onCommit={commitPrice}
          />
        ) : (
          <span
            className="tabular-nums text-muted-foreground"
            title={isBlank ? t('project.samataTemplate.priceAfterQty') : undefined}
            style={{ fontSize: 16 }}
          >
            {kaina != null && Number(kaina) > 0 ? eur.format(Number(kaina)) : '—'}
          </span>
        )}
      </td>
      <td className="px-3 py-2 text-right font-semibold tabular-nums align-top" style={{ fontSize: 16 }}>
        {suma != null && (ownAmount || Number(kaina) > 0) ? eur.format(suma) : ''}
      </td>
      <td className="px-2 py-2 text-right align-top whitespace-nowrap">
        {isSuggested && (
          <button
            type="button"
            onClick={accept}
            title={t('project.samataTemplate.acceptTitle')}
            className={`${SMALL_BTN} border-accent-2 bg-accent-2 text-white hover:opacity-95 mr-1`}
            style={{ minHeight: 44, fontSize: 14 }}
          >
            <Check className="w-4 h-4" />
            {t('project.samataTemplate.accept')}
          </button>
        )}
        {(isSuggested || (isKita && row._saltinio_id?.length) || (row._pildymas === FILL.DONE && !typed && row._saltinio_id?.length)) && (
          <button
            type="button"
            onClick={openSource}
            title={t('project.samataTemplate.fixTitle')}
            className={`${SMALL_BTN} border-border bg-card text-foreground/80 hover:bg-muted/60`}
            style={{ minHeight: 44, fontSize: 14 }}
          >
            <Pencil className="w-3.5 h-3.5" />
            {isSuggested ? t('project.samataTemplate.fix') : t('project.samataTemplate.how')}
          </button>
        )}
      </td>
    </tr>
  );
}

export default function SamataTemplateView({ project, darbai, onDarbaiChange, onOpenLedger, templateId }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);
  const fingerprint = darbaiFingerprint(darbai);
  const projectId = project?.id;
  // The render reads the rows the SCREEN holds (the store lags a keystroke).
  // A ref keeps `load` stable; the effect below decides WHEN to call it.
  const latest = useRef({ darbai, rooms: roomsForRender(project) });
  useEffect(() => { latest.current = { darbai, rooms: roomsForRender(project) }; });

  const load = useCallback((signal) => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    renderSamata(projectId, {
      templateId, rows: latest.current.darbai, rooms: latest.current.rooms, signal,
    })
      .then((body) => { if (!signal.aborted) { setRows(body.eilutes || []); setLoading(false); } })
      .catch((err) => {
        if (signal.aborted) return;
        setError(err?.message || String(err));
        setLoading(false);
      });
  }, [projectId, templateId]);

  // Re-render whenever something the render reads has moved. A short delay
  // coalesces a burst of keystrokes into one request.
  useEffect(() => {
    const ctl = new AbortController();
    const timer = setTimeout(() => load(ctl.signal), 150);
    return () => { clearTimeout(timer); ctl.abort(); };
  }, [load, fingerprint, nonce]);

  const groups = useMemo(() => groupBySection(rows || []), [rows]);
  const summary = useMemo(() => summarize(rows || []), [rows]);
  const total = useMemo(() => (rows || []).reduce((s, r) => s + (lineAmount(r) ?? 0), 0), [rows]);

  const change = (next) => onDarbaiChange(next);

  if (error) {
    return (
      <div className="p-6 text-foreground" style={{ fontSize: 15 }}>
        <p>{t('project.samataTemplate.loadError', { msg: error })}</p>
        <button
          type="button"
          onClick={() => setNonce((n) => n + 1)}
          className="mt-3 inline-flex items-center rounded border border-border bg-card px-3 font-medium hover:bg-muted/60"
          style={{ minHeight: 44 }}
        >
          {t('project.samataTemplate.retry')}
        </button>
      </div>
    );
  }

  if (rows == null) {
    return (
      <p className="p-6 flex items-center gap-2 text-muted-foreground" style={{ fontSize: 15 }}>
        <Loader2 className="w-4 h-4 animate-spin" />
        {t('project.samataTemplate.loading')}
      </p>
    );
  }

  return (
    <div>
      <div className="px-4 py-2.5 border-b border-border bg-muted/10 text-foreground/85 flex items-center gap-2 flex-wrap" style={{ fontSize: 15 }}>
        <span>
          {t('project.samataTemplate.summary', {
            filled: summary.uzpildyta, total: summary.sablonoEilutes,
            suggested: summary.pasiulyta, blank: summary.tuscia,
          })}
        </span>
        {summary.kitosEilutes > 0 && (
          <span className="text-muted-foreground">
            · {t('project.samataTemplate.summaryOther', { count: summary.kitosEilutes })}
          </span>
        )}
        {loading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" aria-hidden />}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full" style={{ fontSize: 16 }}>
          <thead className="text-xs uppercase text-muted-foreground border-b border-border bg-muted/20">
            <tr>
              <th className="px-3 py-2 text-left font-medium w-12">{t('project.samataTemplate.colNr')}</th>
              <th className="px-3 py-2 text-left font-medium">{t('project.samataTemplate.colDescription')}</th>
              <th className="px-3 py-2 text-left font-medium w-20">{t('project.samataTemplate.colUnit')}</th>
              <th className="px-3 py-2 text-right font-medium w-28">{t('project.samataTemplate.colQty')}</th>
              <th className="px-3 py-2 text-right font-medium w-28">{t('project.samataTemplate.colPrice')}</th>
              <th className="px-3 py-2 text-right font-medium w-28">{t('project.samataTemplate.colTotal')}</th>
              <th className="w-44" />
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <SectionRows
                key={g.label}
                group={g}
                darbai={darbai}
                onDarbaiChange={change}
                onOpenLedger={onOpenLedger}
              />
            ))}
          </tbody>
          <tfoot className="border-t-2 border-border bg-muted/20">
            <tr>
              <td colSpan={5} className="px-3 py-2.5 text-right text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {t('project.samataTemplate.totalNoVat')}
              </td>
              <td className="px-3 py-2.5 text-right text-base font-bold tabular-nums text-foreground">
                {eur.format(total)}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

function SectionRows({ group, darbai, onDarbaiChange, onOpenLedger }) {
  return (
    <>
      <tr className="bg-muted/40">
        <td colSpan={7} className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-foreground">
          {group.label}
        </td>
      </tr>
      {group.rows.map((row) => (
        <Row
          key={row.id}
          row={row}
          darbai={darbai}
          onDarbaiChange={onDarbaiChange}
          onOpenLedger={onOpenLedger}
        />
      ))}
    </>
  );
}
