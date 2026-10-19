/**
 * QuestionBodies — what a person answers WITH, one body per answer form of Patikra's question list
 * (backend/extractor/project_questions.py `answer`):
 *
 *   number_all — one number for every room that asked (the ceiling height), a field per room on request;
 *   numbers    — a list of rooms, each with the program's number in a field (perimeters, areas);
 *   choices    — a list of rooms, each with the program's choice pressed (floor covering, painted or not);
 *   openings   — the openings the walls show and the list lacks, ticked — untick what is not a door; and the
 *                rooms whose doors and windows no tick settles, each with the list's and the walls' number and
 *                a field per kind pre-filled with the walls' (2026-10-19 — answered here, never on another page);
 *   outline    — a room to point at on the drawing: the outline the program PROPOSES when the walls close a
 *                different area than the table gives (2026-09-23, objektas_h tambūras), „Tinka" or a click
 *                elsewhere — and always the way without a click, the wall length typed by hand.
 *   reconcile  — the drawing's schedule against what the walls show (Pathon v3 W3-A `lentele_durys` / `lentele_langai`):
 *                which count is right, the proposal (as drawn) pressed, the schedule one click away on the drawing;
 *   info       — a table's own sum against the rooms' (`lentele_suma`): read it, see it on the drawing, „Supratau".
 *
 * „Programa siūlo — jūs patvirtinate": every body opens filled in with the proposal, so the usual action is the
 * one big button. All of them report through `onAnswer(payload)`; the page turns the payload into the project
 * (lib/questions.js). The two drawing answers (`outline`, `split`) live with the drawing, in the page.
 */

import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, MapPin, MousePointerClick } from 'lucide-react';

import { isValidAmount, parseLtNumber } from '@/lib/parseLtNumber';
import { ltNumber } from '@/lib/ledger';
import { cleanUserText } from '@/lib/userText';
import { API_BASE } from '@/lib/apiBase';
import { countChangeText, setOpeningCount } from '@/lib/openingCounts';

export const Q_BTN = 'inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-[2px] border px-4 '
  + 'text-[15px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 '
  + 'focus-visible:ring-ring disabled:opacity-50';
export const Q_PRIMARY = `${Q_BTN} border-accent-2 bg-accent-2 text-white hover:opacity-95`;
export const Q_PLAIN = `${Q_BTN} border-border bg-card hover:bg-muted`;

const INPUT = 'h-11 w-28 rounded-[2px] border border-border bg-card px-2 text-right font-mono text-[16px] '
  + 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
const SMALL_INPUT = 'h-10 w-20 rounded-[2px] border border-border bg-card px-2 text-right font-mono text-[15px] '
  + 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
const SELECT = 'h-10 rounded-[2px] border border-border bg-card px-2 text-[15px] '
  + 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
// an interior door this wide or this narrow is unusual — said beside the opening, he decides (2026-09-23)
const DOOR_WIDTH_M = { min: 0.6, max: 1.2 };

const lt = (v) => (v == null || v === '' ? '' : ltNumber(Number(v), 2));
const roomLabel = (item) => [item.room_nr, item.room_name].filter(Boolean).join(' ');

/**
 * „Rodyti brėžinyje" for a schedule's row or table (`where = {page, rect_pct}`): inside the workspace the drawing
 * jumps there and frames it (`onShow`); on its own page the crop of the table opens under the button.
 */
export function TablePeek({ where, onShow = null, projectId = null, compact = false }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const rect = Array.isArray(where?.rect_pct) && where.rect_pct.length === 4 ? where.rect_pct : null;
  if (!where?.page || !rect) return null;
  const crop = projectId
    ? `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/evidence?page=${Number(where.page)}&rect=${rect.map((v) => Number(v).toFixed(4)).join(',')}&dpi=110`
    : null;
  return (
    <span className="inline-flex flex-col items-start gap-1.5">
      <button
        type="button"
        className={`${Q_PLAIN} ${compact ? 'min-h-[36px] px-3 text-[14px]' : ''}`}
        onClick={() => (onShow ? onShow({ page: Number(where.page), rect_pct: rect }) : setOpen((v) => !v))}
        data-testid="question-show-table"
      >
        <MapPin className="h-4 w-4" aria-hidden="true" />
        {t('project.questions.showOnDrawing')}
      </button>
      {!onShow && open && crop && (
        <img src={crop} alt={`Lentelė, ${where.page} lapas`} className="max-h-72 max-w-full rounded-[2px] border border-border bg-white object-contain" />
      )}
    </span>
  );
}

/** Which of two counts is right — the schedule's or the walls' — with the schedule one click away. */
export function ReconcileBody({ question, busy, onAnswer, onShowTable = null, projectId = null }) {
  const { t } = useTranslation();
  const [picked, setPicked] = useState(null);
  useEffect(() => { setPicked(null); }, [question.id]);
  const current = picked ?? question.proposed;
  const edited = picked != null && picked !== question.proposed;
  return (
    <div className="flex flex-col gap-3" data-testid="question-reconcile">
      <div className="flex flex-wrap gap-1.5" role="group" aria-label={question.title}>
        {(question.choices || []).map((c) => (
          <button
            key={String(c.value)} type="button" aria-pressed={current === c.value}
            onClick={() => setPicked(c.value)}
            className={`inline-flex min-h-[44px] items-center rounded-[2px] border px-3 text-[15px] font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
              ${current === c.value ? 'border-accent-2 bg-accent-2/10 text-accent-2' : 'border-border bg-card hover:bg-muted'}`}
            data-testid={`reconcile-${c.value}`}
          >
            {c.label}
          </button>
        ))}
      </div>
      {Array.isArray(question.items) && question.items.length > 0 && (
        <ul className="rounded-[2px] border border-border">
          {question.items.map((item) => (
            <li key={item.room_nr} className="flex flex-wrap items-baseline justify-between gap-x-3 border-t border-border px-3 py-2 first:border-t-0 text-[14px]">
              <span className="font-semibold"><span className="font-mono text-muted-foreground">{item.room_nr}</span> {item.room_name}</span>
              <span className="text-ink-2">{cleanUserText(item.sentence || '')}</span>
            </li>
          ))}
        </ul>
      )}
      {question.lentele?.sentence && <p className="text-[14px] leading-snug text-ink-2">{cleanUserText(question.lentele.sentence)}</p>}
      <div className="flex flex-wrap items-start gap-2">
        <button type="button" className={Q_PRIMARY} disabled={busy} data-testid="question-accept" onClick={() => onAnswer({ value: current })}>
          <Check className="h-4 w-4" aria-hidden="true" />
          {edited ? t('project.questions.save') : t('project.questions.accept')}
        </button>
        <TablePeek where={question.lentele} onShow={onShowTable} projectId={projectId} />
      </div>
    </div>
  );
}

/** A difference to know about, not to decide: see it on the drawing, then „Supratau". */
export function InfoBody({ question, busy, onAnswer, onShowTable = null, projectId = null }) {
  const { t } = useTranslation();
  const item = (question.items || [])[0] || {};
  const unit = question.unit || '';
  return (
    <div className="flex flex-col gap-3" data-testid="question-info">
      {item.lentele != null && item.musu != null && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-[2px] border border-border px-3 py-2 text-[15px]">
          <dt className="text-ink-2">{item.room_name || 'Lentelėje'}</dt>
          <dd className="font-mono tabular-nums">{lt(item.lentele)} {unit}</dd>
          <dt className="text-ink-2">Patalpų suma</dt>
          <dd className="font-mono tabular-nums">{lt(item.musu)} {unit}</dd>
        </dl>
      )}
      <div className="flex flex-wrap items-start gap-2">
        <button type="button" className={Q_PRIMARY} disabled={busy} data-testid="question-accept" onClick={() => onAnswer({ value: 'matyta' })}>
          <Check className="h-4 w-4" aria-hidden="true" />
          {t('project.questions.infoSeen')}
        </button>
        <TablePeek where={question.lentele || { page: item.page, rect_pct: item.rect_pct }} onShow={onShowTable} projectId={projectId} />
      </div>
    </div>
  );
}

function Row({ item, focused, onFocus, children, note, stacked = false }) {
  return (
    <li
      className={`border-t border-border first:border-t-0 ${focused ? 'bg-accent-2/[0.06]' : ''}`}
      data-testid={`question-item-${item.room_nr}`}
    >
      {/* `stacked`: a row of wide choice buttons goes UNDER the room's name — beside it the name broke into three lines */}
      <div className={stacked ? 'flex flex-col items-start gap-1.5 px-3 py-2' : 'flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-3 py-2'}>
        <button
          type="button"
          onClick={() => onFocus?.(item.room_nr)}
          className={`min-w-0 text-left text-[15px] font-semibold text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${stacked ? '' : 'flex-1'}`}
        >
          <span className="font-mono text-muted-foreground">{item.room_nr}</span>{' '}
          {item.room_name}
        </button>
        <div className="flex items-center gap-2">{children}</div>
      </div>
      {focused && note && <p className="px-3 pb-2 text-[13px] leading-snug text-ink-2">{note}</p>}
    </li>
  );
}

/**
 * A room to point at on the drawing. With a proposal: the sentence says what the walls close around the room's
 * number and why the program did not take it itself; „Tinka" takes it, a click elsewhere replaces it. Always:
 * the wall length typed by hand — the answer when no click can find the room.
 */
export function OutlineBody({ question, item, busy, onAccept, onTypeLength }) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(() => lt(item?.perimetras_dabar));
  useEffect(() => { setDraft(lt(item?.perimetras_dabar)); }, [item?.room_nr, item?.perimetras_dabar]);
  if (!item) return <p className="text-[15px] text-ink-2">{t('project.questions.outlineAllSkipped')}</p>;
  const value = parseLtNumber(draft);
  const valid = isValidAmount(value);
  const proposal = item.proposed_outline;
  const commit = () => { if (valid) onTypeLength?.(value); };
  return (
    <div className="flex flex-col gap-3">
      <p className="text-[15px] font-semibold">
        {question.items.length > 1 && `${question.items.indexOf(item) + 1} / ${question.items.length} · `}
        <span className="font-mono text-muted-foreground">{item.room_nr}</span> {item.room_name}
      </p>
      {proposal ? (
        <>
          <p className="text-[14px] leading-snug text-ink-2" data-testid="outline-proposal-sentence">
            {cleanUserText(item.sentence || '')}
          </p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <button type="button" className={Q_PRIMARY} disabled={busy} data-testid="question-accept" onClick={onAccept}>
              <Check className="h-4 w-4" aria-hidden="true" />
              {t('project.questions.outlineAccept', { area: ltNumber(Number(proposal.plotas_m2), 2) })}
            </button>
            <span className="text-[14px] leading-snug text-ink-2">{t('project.questions.outlineElsewhere')}</span>
          </div>
        </>
      ) : (
        <>
          <p className="text-[14px] leading-snug text-ink-2">
            {t('project.questions.outlineReason', { reason: cleanUserText(item.reason || '').replace(/\.$/, '') })}
          </p>
          <p className="text-[14px] leading-snug text-ink-2">{t('project.questions.outlineHow')}</p>
        </>
      )}
      <div className="border-t border-border pt-3">
        <p className="text-[14px] leading-snug text-ink-2">{t('project.questions.outlineTypeLength')}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <label className="text-[15px] text-ink-2" htmlFor="q-outline-length">{t('project.questions.outlineLengthLabel')}</label>
          <input
            id="q-outline-length" value={draft} inputMode="decimal" className={INPUT}
            onFocus={(e) => e.target.select()}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commit(); } }}
          />
          <button type="button" className={Q_PLAIN} disabled={busy || !valid} onClick={commit} data-testid="outline-type-length">
            {t('project.questions.save')}
          </button>
        </div>
        {!valid && draft !== '' && <p className="mt-1 text-[13px] text-conf-low">{t('project.questions.needNumber')}</p>}
      </div>
    </div>
  );
}

/** One number for every room that asked; „Kai kur kitaip?" opens a field per room. */
export function NumberAllBody({ question, busy, onAnswer }) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(() => lt(question.proposed));
  const [separately, setSeparately] = useState(false);
  const [own, setOwn] = useState({});
  useEffect(() => { setDraft(lt(question.proposed)); setSeparately(false); setOwn({}); }, [question.id, question.proposed]);

  const value = parseLtNumber(draft);
  const valid = isValidAmount(value);
  const n = question.items.length;
  const commit = () => {
    if (!valid) return;
    const perRoom = {};
    if (separately) {
      for (const [nr, text] of Object.entries(own)) {
        const num = parseLtNumber(text);
        if (isValidAmount(num)) perRoom[nr] = num;
      }
    }
    onAnswer({ value, perRoom });
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-[15px] text-ink-2" htmlFor="q-number-all">{t('project.questions.heightLabel')}</label>
        <input
          id="q-number-all" value={draft} inputMode="decimal" className={INPUT}
          onFocus={(e) => e.target.select()}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commit(); } }}
        />
        <button type="button" className={Q_PRIMARY} disabled={busy || !valid} onClick={commit} data-testid="question-accept">
          <Check className="h-4 w-4" aria-hidden="true" />
          {n === 1 ? t('project.questions.accept')
            : separately && Object.values(own).some((v) => v !== '' && v !== draft) ? t('project.questions.save')
              : t('project.questions.acceptAllRooms', { count: n })}
        </button>
      </div>
      {!valid && draft !== '' && <p className="text-[13px] text-conf-low">{t('project.questions.needNumber')}</p>}

      <div>
        <p className="text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">{t('project.questions.roomsAsked')}</p>
        {!separately && (
          <p className="mt-1 text-[15px] leading-relaxed text-foreground">
            {question.items.map(roomLabel).join(' · ')}
          </p>
        )}
        {separately && (
          <ul className="mt-1 rounded-[2px] border border-border">
            {question.items.map((item) => (
              <Row key={item.room_nr} item={item}>
                <input
                  value={own[item.room_nr] ?? draft} inputMode="decimal" className={INPUT}
                  aria-label={`${roomLabel(item)} — ${t('project.questions.heightLabel')}`}
                  onFocus={(e) => e.target.select()}
                  onChange={(e) => setOwn((cur) => ({ ...cur, [item.room_nr]: e.target.value }))}
                />
                <span className="text-[14px] text-muted-foreground">m</span>
              </Row>
            ))}
          </ul>
        )}
        {n > 1 && (
          <button
            type="button"
            className="mt-2 text-[14px] font-semibold text-accent-2 underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => setSeparately((v) => !v)}
          >
            {separately ? t('project.questions.elsewhereHide') : t('project.questions.elsewhere')}
          </button>
        )}
      </div>
    </div>
  );
}

/** Rooms with the program's number in a field each. */
export function NumbersBody({ question, busy, focusNr, onFocus, onAnswer }) {
  const { t } = useTranslation();
  const [drafts, setDrafts] = useState({});
  useEffect(() => { setDrafts({}); }, [question.id]);

  const parsed = useMemo(() => {
    const out = {};
    for (const [nr, text] of Object.entries(drafts)) {
      if (text === '') continue;
      out[nr] = parseLtNumber(text);
    }
    return out;
  }, [drafts]);
  const bad = Object.values(parsed).some((v) => !isValidAmount(v));
  const edited = Object.keys(parsed).length > 0;
  const answerable = question.items.some((i) => isValidAmount(parsed[i.room_nr] ?? i.proposed));
  const n = question.items.length;

  return (
    <div className="flex flex-col gap-3">
      <ul className="rounded-[2px] border border-border">
        {question.items.map((item) => (
          <Row key={item.room_nr} item={item} focused={focusNr === item.room_nr} onFocus={onFocus} note={cleanUserText(item.sentence || '')}>
            <input
              value={drafts[item.room_nr] ?? lt(item.proposed)} inputMode="decimal" className={INPUT}
              aria-label={roomLabel(item)}
              onFocus={(e) => { e.target.select(); onFocus?.(item.room_nr); }}
              onChange={(e) => setDrafts((cur) => ({ ...cur, [item.room_nr]: e.target.value }))}
            />
            <span className="w-7 text-[14px] text-muted-foreground">{question.unit}</span>
          </Row>
        ))}
      </ul>
      {bad && <p className="text-[13px] text-conf-low">{t('project.questions.needNumber')}</p>}
      <div>
        <button
          type="button" className={Q_PRIMARY} disabled={busy || bad || !answerable} data-testid="question-accept"
          onClick={() => onAnswer({ values: parsed })}
        >
          <Check className="h-4 w-4" aria-hidden="true" />
          {edited ? t('project.questions.save') : n === 1 ? t('project.questions.accept') : t('project.questions.acceptAll', { count: n })}
        </button>
      </div>
    </div>
  );
}

/** Rooms with the program's choice pressed. */
export function ChoicesBody({ question, busy, focusNr, onFocus, onAnswer, onShowTable = null, projectId = null }) {
  const { t } = useTranslation();
  const [picked, setPicked] = useState({});
  useEffect(() => { setPicked({}); }, [question.id]);
  const edited = Object.keys(picked).length > 0;
  const n = question.items.length;

  return (
    <div className="flex flex-col gap-3">
      <ul className="rounded-[2px] border border-border">
        {question.items.map((item) => {
          const current = picked[item.room_nr] ?? item.proposed;
          return (
            <Row key={item.room_nr} item={item} focused={focusNr === item.room_nr} onFocus={onFocus} note={cleanUserText(item.sentence || '')} stacked>
              <div className="flex flex-wrap gap-1" role="group" aria-label={roomLabel(item)}>
                {(item.choices || []).map((c) => (
                  <button
                    key={String(c.value)} type="button" aria-pressed={current === c.value}
                    onClick={() => { onFocus?.(item.room_nr); setPicked((cur) => ({ ...cur, [item.room_nr]: c.value })); }}
                    className={`inline-flex min-h-[36px] items-center rounded-[2px] border px-2.5 text-[14px] font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
                      ${current === c.value ? 'border-accent-2 bg-accent-2/10 text-accent-2' : 'border-border bg-card hover:bg-muted'}`}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
              {/* the schedule's row this choice was read from (v3 W3-A `lentele_apdaila`, a floor proposed from the table) */}
              {focusNr === item.room_nr && (
                <TablePeek where={item.rect_pct ? { page: item.page, rect_pct: item.rect_pct } : item.lentele} onShow={onShowTable} projectId={projectId} compact />
              )}
            </Row>
          );
        })}
      </ul>
      <div>
        <button type="button" className={Q_PRIMARY} disabled={busy} data-testid="question-accept" onClick={() => onAnswer({ values: picked })}>
          <Check className="h-4 w-4" aria-hidden="true" />
          {edited ? t('project.questions.save') : n === 1 ? t('project.questions.accept') : t('project.questions.acceptAll', { count: n })}
        </button>
      </div>
    </div>
  );
}

/** One count field of a room to check: the two numbers, the field, and what „Tinka" will do with it. */
function CountField({ row, kind, value, onChange, onCommit, room, busy }) {
  const { t } = useTranslation();
  const nums = row[kind] || { sarase: 0, sienose: 0, laisvos: [] };
  const n = Number(String(value).trim());
  const valid = String(value).trim() !== '' && Number.isInteger(n) && n >= 0 && n <= 50;
  const effect = valid ? setOpeningCount(room?.elementai || [], kind, n, nums.laisvos) : null;
  const id = `q-count-${row.room_nr}-${kind}`;
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <label htmlFor={id} className="w-16 text-[15px] font-semibold text-foreground">
          {t(kind === 'durys' ? 'project.questions.countDoors' : 'project.questions.countWindows')}
        </label>
        <input
          id={id} value={value} inputMode="numeric" className={SMALL_INPUT} disabled={busy}
          data-testid={`opening-count-${row.room_nr}-${kind}`}
          onFocus={(e) => e.target.select()}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onCommit(); } }}
        />
        <span className="font-mono text-[14px] text-ink-2" data-testid={`opening-numbers-${row.room_nr}-${kind}`}>
          {t('project.questions.countNumbers', { listed: nums.sarase, walls: nums.sienose })}
        </span>
      </div>
      <p className={`text-[14px] leading-snug ${valid ? 'text-ink-2' : 'text-conf-low'}`} data-testid={`opening-effect-${row.room_nr}-${kind}`}>
        {valid ? countChangeText(effect, kind) : t('project.questions.needWhole')}
      </p>
    </div>
  );
}

/**
 * The openings the walls show and the list lacks — ticked; and the rooms whose doors and windows no tick settles,
 * each answered on the card: the number of doors and of windows (the walls' number proposed), „Rodyti brėžinyje"
 * frames the room on the drawing beside, „Pažymėti brėžinyje" lets him click its openings there. One „Tinka".
 */
export function OpeningsBody({
  question, busy, focusNr, onFocus, onAnswer, rooms = [], onShowRoom = null, onPlaceOnDrawing = null, placingNr = null,
}) {
  const { t } = useTranslation();
  const [off, setOff] = useState(() => new Set());
  const [edits, setEdits] = useState({});                       // index → {plotis, aukstis, tipas} as he typed them
  const [counts, setCounts] = useState({});                     // room nr → {durys, langai} as he typed them
  useEffect(() => { setOff(new Set()); setEdits({}); setCounts({}); }, [question.id, question.items.length, question.manual?.length]);
  const manual = Array.isArray(question.manual) ? question.manual : [];
  const roomOf = (nr) => (Array.isArray(rooms) ? rooms : []).find((r) => String(r?.nr) === String(nr)) || null;
  const countOf = (row, kind) => counts[row.room_nr]?.[kind] ?? String(row.proposed?.[kind] ?? row[kind]?.sienose ?? 0);
  const countsValid = manual.every((row) => ['durys', 'langai'].every((kind) => {
    const v = String(countOf(row, kind)).trim();
    const n = Number(v);
    return v !== '' && Number.isInteger(n) && n >= 0 && n <= 50;
  }));
  const countsEdited = manual.some((row) => ['durys', 'langai'].some((kind) => counts[row.room_nr]?.[kind] !== undefined
    && String(counts[row.room_nr][kind]).trim() !== String(row.proposed?.[kind] ?? '')));
  const count = question.items.length - off.size;
  const draftOf = (item, i) => ({
    plotis: edits[i]?.plotis ?? ltNumber(Number(item.plotis_mm) / 1000, 2),
    aukstis: edits[i]?.aukstis ?? ltNumber(Number(item.aukstis_mm) / 1000, 2),
    tipas: edits[i]?.tipas ?? (item.tipas === 'langas' ? 'langas' : 'duris'),
  });
  const setEdit = (i, patch) => setEdits((cur) => ({ ...cur, [i]: { ...(cur[i] || {}), ...patch } }));
  const toggle = (i, item) => { onFocus?.(item.room_nr); setOff((cur) => { const next = new Set(cur); if (next.has(i)) next.delete(i); else next.add(i); return next; }); };
  const commit = () => {
    const out = {};
    question.items.forEach((item, i) => {
      const d = draftOf(item, i);
      const w = parseLtNumber(d.plotis);
      const h = parseLtNumber(d.aukstis);
      out[i] = {
        plotis_mm: isValidAmount(w) ? Math.round(w * 1000) : item.plotis_mm,
        aukstis_mm: isValidAmount(h) ? Math.round(h * 1000) : item.aukstis_mm,
        tipas: d.tipas,
      };
    });
    const typed = {};
    for (const row of manual) typed[row.room_nr] = { durys: Number(countOf(row, 'durys')), langai: Number(countOf(row, 'langai')) };
    onAnswer({ picked: question.items.map((_, i) => !off.has(i)), edits: out, counts: typed });
  };
  const commitIfValid = () => { if (!busy && countsValid && (count > 0 || manual.length > 0)) commit(); };

  return (
    <div className="flex flex-col gap-3">
      {question.items.length > 0 && (
        <>
          <ul className="rounded-[2px] border border-border">
            {question.items.map((item, i) => {
              const d = draftOf(item, i);
              const w = parseLtNumber(d.plotis);
              const leads = String(item.label || '').includes('—') ? cleanUserText(String(item.label).split('—').slice(1).join('—').trim()) : '';
              const odd = d.tipas === 'duris' && item.i !== 'laukas' && isValidAmount(w) && (w > DOOR_WIDTH_M.max || w < DOOR_WIDTH_M.min);
              const badNumber = (d.plotis !== '' && !isValidAmount(w)) || (d.aukstis !== '' && !isValidAmount(parseLtNumber(d.aukstis)));
              return (
                <li
                  key={`${item.room_nr}-${item.i}-${item.plotis_mm}-${i}`}
                  className={`border-t border-border first:border-t-0 ${focusNr === item.room_nr ? 'bg-accent-2/[0.06]' : ''}`}
                  data-testid={`opening-item-${item.room_nr}-${i}`}
                >
                  <div className="flex items-start gap-3 px-3 py-2.5">
                    <input
                      type="checkbox" className="mt-1 h-5 w-5 shrink-0 accent-accent-2" checked={!off.has(i)}
                      aria-label={`${roomLabel(item)} — ${t('project.questions.openingTicked')}`}
                      onChange={() => toggle(i, item)}
                    />
                    <div className="min-w-0 flex-1">
                      <button
                        type="button" onClick={() => onFocus?.(item.room_nr)}
                        className="text-left text-[15px] font-semibold leading-snug focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <span className="font-mono text-muted-foreground">{item.room_nr}</span> {item.room_name}
                        {leads && <span className="font-normal text-ink-2"> — {leads}</span>}
                      </button>
                      {/* the width the walls show and the standard height — both his to correct, and the kind
                          (2026-09-23: „durys 1,40 pločio nebus tikrai … turi būti galimybė pataisyti") */}
                      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[14px] text-ink-2">
                        <select
                          value={d.tipas} className={SELECT} aria-label={`${roomLabel(item)} — ${t('project.questions.openingKind')}`}
                          onChange={(e) => setEdit(i, { tipas: e.target.value })}
                        >
                          <option value="duris">{t('project.questions.kindDoor')}</option>
                          <option value="langas">{t('project.questions.kindWindow')}</option>
                        </select>
                        <input
                          value={d.plotis} inputMode="decimal" className={SMALL_INPUT}
                          aria-label={`${roomLabel(item)} — ${t('project.questions.openingWidth')}`}
                          onFocus={(e) => e.target.select()} onChange={(e) => setEdit(i, { plotis: e.target.value })}
                        />
                        <span aria-hidden="true">×</span>
                        <input
                          value={d.aukstis} inputMode="decimal" className={SMALL_INPUT}
                          aria-label={`${roomLabel(item)} — ${t('project.questions.openingHeight')}`}
                          onFocus={(e) => e.target.select()} onChange={(e) => setEdit(i, { aukstis: e.target.value })}
                        />
                        <span>m</span>
                      </div>
                      {odd && !off.has(i) && (
                        <p className="mt-1 text-[13px] leading-snug text-conf-low" data-testid="opening-width-odd">
                          {t('project.questions.openingWidthOdd', { width: d.plotis })}
                        </p>
                      )}
                      {badNumber && <p className="mt-1 text-[13px] leading-snug text-conf-low">{t('project.questions.needNumber')}</p>}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {manual.length > 0 && (
        <div>
          {question.items.length > 0 && (
            <p className="text-[15px] font-semibold text-foreground">{t('project.questions.manualTitle')}</p>
          )}
          <ul className={`${question.items.length > 0 ? 'mt-1 ' : ''}rounded-[2px] border border-border`}>
            {manual.map((m) => (
              <li
                key={m.room_nr}
                className={`border-t border-border px-3 py-2.5 first:border-t-0 ${focusNr === m.room_nr ? 'bg-accent-2/[0.06]' : ''}`}
                data-testid={`opening-manual-${m.room_nr}`}
              >
                <div className="flex flex-col items-start gap-1.5">
                  <button
                    type="button" onClick={() => onFocus?.(m.room_nr)}
                    className="min-w-0 text-left text-[15px] font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span className="font-mono text-muted-foreground">{m.room_nr}</span> {m.room_name}
                  </button>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button" className={`${Q_PLAIN} min-h-[36px] px-3 text-[14px]`} disabled={busy}
                      onClick={() => onShowRoom?.(m)} data-testid={`opening-show-${m.room_nr}`}
                    >
                      <MapPin className="h-4 w-4" aria-hidden="true" />
                      {t('project.questions.showOnDrawing')}
                    </button>
                    {onPlaceOnDrawing && Number(m.angos_brezinyje) > 0 && (
                      <button
                        type="button" aria-pressed={placingNr === m.room_nr} disabled={busy}
                        className={`${Q_PLAIN} min-h-[36px] px-3 text-[14px] ${placingNr === m.room_nr ? 'border-accent-2 bg-accent-2/[0.08]' : ''}`}
                        onClick={() => onPlaceOnDrawing(placingNr === m.room_nr ? null : m.room_nr)}
                        data-testid={`opening-place-${m.room_nr}`}
                      >
                        <MousePointerClick className="h-4 w-4" aria-hidden="true" />
                        {t(placingNr === m.room_nr ? 'project.questions.placeStop' : 'project.questions.placeOnDrawing')}
                      </button>
                    )}
                  </div>
                </div>
                {/* what does not match, in his terms; the fields answer it right here */}
                <p className="mt-1 text-[15px] leading-snug text-foreground">{cleanUserText(m.sentence || '')}</p>
                <div className="mt-2 flex flex-col gap-2">
                  {['durys', 'langai'].map((kind) => (
                    <CountField
                      key={kind} row={m} kind={kind} value={countOf(m, kind)} room={roomOf(m.room_nr)} busy={busy}
                      onChange={(v) => setCounts((cur) => ({ ...cur, [m.room_nr]: { ...(cur[m.room_nr] || {}), [kind]: v } }))}
                      onCommit={commitIfValid}
                    />
                  ))}
                </div>
                {m.details && (
                  <details className="mt-1.5 text-[13px] leading-snug text-ink-2">
                    <summary className="cursor-pointer select-none text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                      {t('project.questions.manualDetails')}
                    </summary>
                    <p className="mt-1">{cleanUserText(m.details)}</p>
                  </details>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <button
          type="button" className={Q_PRIMARY} disabled={busy || !countsValid || (count === 0 && manual.length === 0)}
          data-testid="question-accept" onClick={commit}
        >
          <Check className="h-4 w-4" aria-hidden="true" />
          {question.items.length > 0
            ? t(manual.length ? 'project.questions.addPickedAndCounts' : 'project.questions.addPicked', { count })
            : countsEdited ? t('project.questions.save')
              : manual.length === 1 ? t('project.questions.accept') : t('project.questions.acceptAll', { count: manual.length })}
        </button>
        <p className="mt-1 text-[13px] leading-snug text-muted-foreground">{t('project.questions.openingsConsequence')}</p>
      </div>
    </div>
  );
}
