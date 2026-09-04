/**
 * PatikraCard — one claim, one decision.
 *
 * The rail walks the contractor down the queue that `rankReviewRows` orders by
 * what a wrong line COSTS (€ impact × confidence), and each stop is this card:
 * the number, the chain that produced it, the single input it leans on hardest,
 * and two verbs — „Teisinga ✓" (the row is verified, and that verification is
 * also the ground-truth corpus) or „Pataisyti" (jump to the control that
 * changes the input, not to the number).
 *
 * Derivation before checkmark, deliberately: the measured false-green rate was
 * 50–60 %, so a card that offered a ✓ without showing where the number came
 * from would train exactly the rubber-stamping it is meant to prevent
 * (`extractor/confidence.py:1–22`).
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Check, MapPin, Pencil, Sigma } from 'lucide-react';
import { CONFIDENCE_DOT_CLASS, confidenceLabel, normalizeConfidence } from '@/lib/confidence';
import { ltEur, ltNumber, ltQuantity, rollUpHeadline } from '@/lib/ledger';
import { parseLtNumber, isValidAmount } from '@/lib/parseLtNumber';
import { cleanUserText } from '@/lib/userText';

export default function PatikraCard({
  row,
  sensitive = null,
  onAccept = null,
  onFix = null,
  onWhy = null,
  onFocusRoom = null,
  onQuantityChange = null,
}) {
  const { t } = useTranslation();
  const [draftQty, setDraftQty] = useState('');
  const [editingQty, setEditingQty] = useState(false);

  const tier = normalizeConfidence(row?.confidence);
  const unit = row?.mato_vnt || row?.vnt;
  const suma = (Number(row?.kiekis) || 0) * (Number(row?.kaina) || 0);
  const headline = rollUpHeadline(row?.roll_up, unit);
  // With no fix surface behind the sensitive input, „Pataisyti" edits the
  // quantity in place — the last honest option, never a dead button.
  const fixesQuantity = !sensitive || sensitive.kind === 'reason' || !onFix;

  const commitQty = () => {
    const num = parseLtNumber(draftQty);
    if (!isValidAmount(num)) return;
    onQuantityChange?.(num);
    setEditingQty(false);
  };

  const startFix = () => {
    if (fixesQuantity) {
      setDraftQty(String(row?.kiekis ?? 0).replace('.', ','));
      setEditingQty(true);
      return;
    }
    onFix(sensitive);
  };

  return (
    <div
      className="rounded-sm"
      style={{
        background: 'hsl(var(--card))',
        border: '1px solid hsl(var(--primary))',
        boxShadow: '0 0 0 1px hsl(var(--primary) / 0.35)',
        padding: '10px 12px',
      }}
    >
      {/* ── The claim ──────────────────────────────────────────────────── */}
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[13px] font-semibold text-foreground min-w-0">
          {row?.aprasymas || row?.pavadinimas}
        </span>
        <span className="mono tabular text-[13px] font-semibold text-foreground whitespace-nowrap">
          {ltQuantity(row?.kiekis, unit)}
        </span>
      </div>
      <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
        {suma > 0 && <span className="mono tabular">≈ {ltEur(suma)}</span>}
        {suma > 0 && <span aria-hidden="true">·</span>}
        <span className={`dot ${CONFIDENCE_DOT_CLASS[tier]}`} />
        <span>{confidenceLabel(tier)}</span>
      </div>

      {/* ── The evidence: the server's own chain ───────────────────────── */}
      {headline && (
        <div
          className="mt-2 rounded-sm px-2.5 py-1.5"
          style={{ background: 'hsl(var(--bg-1))', border: '1px solid hsl(var(--border))' }}
        >
          <span className="flex items-start gap-1.5">
            <Sigma className="w-3 h-3 shrink-0 mt-0.5" style={{ color: 'hsl(var(--primary))' }} />
            <span className="mono tabular text-[11px] leading-relaxed text-foreground">
              {headline}
            </span>
          </span>
        </div>
      )}

      {/* ── „Jautriausia vieta" — the one input to check first ─────────── */}
      {sensitive && (
        <div
          className="mt-2 flex items-start gap-2 text-[11.5px] leading-relaxed"
          style={{
            background: 'hsl(var(--conf-med) / 0.10)',
            borderLeft: '3px solid hsl(var(--conf-med))',
            padding: '6px 9px',
            color: 'hsl(var(--foreground) / 0.9)',
          }}
        >
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" style={{ color: 'hsl(var(--conf-med))' }} />
          <span>
            <strong className="font-semibold">{t('project.patikra.sensitive')}:</strong>{' '}
            <SensitiveText sensitive={sensitive} row={row} />
            {sensitive.page != null && onFocusRoom && (
              <button
                type="button"
                onClick={() => onFocusRoom(sensitive)}
                className="ml-1 inline-flex items-center gap-0.5 align-baseline transition-colors hover:underline"
                style={{ color: 'hsl(var(--primary))' }}
                title={t('project.ledger.pageTitle', { room: sensitive.roomName || sensitive.roomNr })}
              >
                <MapPin className="w-2.5 h-2.5" />
                {t('project.ledger.page', { page: sensitive.page })}
              </button>
            )}
          </span>
        </div>
      )}

      {/* ── The two verbs ─────────────────────────────────────────────── */}
      {editingQty ? (
        <div className="mt-2.5 flex items-center gap-1.5">
          <input
            autoFocus
            onFocus={(e) => e.target.select()}
            value={draftQty}
            onChange={e => setDraftQty(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitQty();
              if (e.key === 'Escape') setEditingQty(false);
            }}
            aria-label={t('project.patikra.quantityAria')}
            title={t('project.patikra.quantityTitle')}
            className="mono tabular flex-1 min-w-0 bg-card border rounded-sm outline-none text-right"
            style={{ fontSize: 12, height: 28, padding: '2px 8px', borderColor: 'hsl(var(--primary))' }}
          />
          <button
            type="button"
            onClick={commitQty}
            className="rounded-sm px-2.5 text-[12px] font-semibold"
            style={{ height: 28, background: 'hsl(var(--primary))', color: 'hsl(var(--primary-foreground))' }}
          >
            {t('project.patikra.save')}
          </button>
          <button
            type="button"
            onClick={() => setEditingQty(false)}
            className="rounded-sm px-2 text-[12px] text-muted-foreground"
            style={{ height: 28, border: '1px solid hsl(var(--border))' }}
          >
            {t('project.patikra.cancel')}
          </button>
        </div>
      ) : (
        <div className="mt-2.5 flex gap-1.5">
          {onAccept && (
            <button
              type="button"
              onClick={onAccept}
              title={t('project.patikra.acceptTitle')}
              className="flex-1 inline-flex items-center justify-center gap-1 rounded-sm text-[12px] font-semibold transition-opacity hover:opacity-90"
              style={{
                height: 28,
                background: 'hsl(var(--primary))',
                color: 'hsl(var(--primary-foreground))',
              }}
            >
              <Check className="w-3.5 h-3.5" />
              {t('project.patikra.accept')}
            </button>
          )}
          <button
            type="button"
            onClick={startFix}
            title={fixesQuantity
              ? t('project.patikra.fixQuantityTitle')
              : t(`project.patikra.fixTitle.${sensitive.kind}`, {
                room: sensitive.roomName || sensitive.roomNr,
              })}
            className="flex-1 inline-flex items-center justify-center gap-1 rounded-sm text-[12px] font-semibold text-foreground transition-colors hover:bg-muted/50"
            style={{ height: 28, border: '1px solid hsl(var(--border))', background: 'hsl(var(--card))' }}
          >
            <Pencil className="w-3.5 h-3.5" />
            {fixesQuantity
              ? t('project.patikra.fixQuantity')
              : t(`project.patikra.fix.${sensitive.kind}`)}
          </button>
        </div>
      )}

      {/* ── The derivation, one click away ─────────────────────────────── */}
      {onWhy && (
        <button
          type="button"
          onClick={onWhy}
          className="mt-2 text-[11px] transition-colors"
          style={{
            color: 'hsl(var(--primary))',
            borderBottom: '1px dotted hsl(var(--primary) / 0.5)',
          }}
        >
          {t('project.patikra.why')}
        </button>
      )}

    </div>
  );
}

/** The sensitive input in one sentence, honest about where the value came from. */
function SensitiveText({ sensitive, row }) {
  const { t } = useTranslation();
  if (sensitive.kind === 'reason') return <>{cleanUserText(sensitive.reason)}</>;

  const room = `${sensitive.roomNr} ${sensitive.roomName || ''}`.trim();
  const value = sensitive.value != null
    ? ltQuantity(sensitive.value, sensitive.unit)
    : t('project.patikra.valueUnknown');
  const share = sensitive.contributionShare;
  return (
    <>
      {t(`project.patikra.sensitiveText.${sensitive.kind}`, { room, value })}{' '}
      <span className="text-muted-foreground">
        {t(sensitive.assumed
          ? 'project.patikra.sourceAssumed'
          : 'project.patikra.sourceRead')}
      </span>
      {share != null && share >= 0.25 && (
        <span className="text-muted-foreground">
          {' '}
          {t('project.patikra.sharesOfLine', {
            pct: ltNumber(share * 100, 0),
            qty: ltQuantity(row?.kiekis, row?.mato_vnt || row?.vnt),
          })}
        </span>
      )}
    </>
  );
}
