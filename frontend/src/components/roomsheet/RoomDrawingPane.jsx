/**
 * RoomDrawingPane — the check sheet's left side on the REAL drawing.
 *
 * Patikra v2 (2026-09-19). Founder, after the first real run: „brėžinyje
 * sunkiai matosi kas pažymėta… lapai blurry… kai kur net nematau pažymėjimų".
 * The pane used to be a server-side raster crop (110–160 dpi); this is the
 * EmbedPDF viewer — sharp at any zoom — with what the program READ about this
 * room drawn on it (lib/checkOverlay → viewer/CheckLayer): the traced outline,
 * every wall coloured by where its length came from with the number along it,
 * the dimension strings that were added, the place each fact was read from.
 *
 * One viewer instance lives across rooms (the PDF engine loads once); a room
 * change or a „show on the drawing" click only changes `check` and `focus`.
 * Hovering a fact lights its mark; it never moves the drawing — a jump is
 * always something he asked for.
 *
 * The raster RoomPlanPane stays as the fallback: phones (the viewer is not
 * shown there in step 1 either), a PDF that is not in storage, an engine that
 * fails. It is the exception now, and the pane says why it is shown.
 */

import { Component, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Maximize2, ScanSearch } from 'lucide-react';
import TakeoffViewer from '@/components/viewer/TakeoffViewer';
import RoomPlanPane from '@/components/roomsheet/RoomPlanPane';
import { getPdfUrl } from '@/lib/pdfStore';
import { buildCheckOverlay } from '@/lib/checkOverlay';
import { laneMastelisOf, pageScalesFromLane } from '@/lib/durableScale';
import { cleanUserText } from '@/lib/userText';

const WALL_LEGEND = [
  ['read', '#15803d', null, 'legendWallRead'],
  ['borrowed', '#b45309', null, 'legendWallBorrowed'],
  ['outline', '#64748b', null, 'legendWallOutline'],
  ['missing', '#dc2626', '5 4', 'legendWallMissing'],
];

const BTN = 'inline-flex min-h-[36px] items-center gap-1.5 rounded-[2px] border border-border bg-card px-3 '
  + 'text-[14px] font-semibold hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

/** The viewer is a third-party engine: if it throws, the sheet keeps working on the raster pane. */
class ViewerBoundary extends Component {
  constructor(props) { super(props); this.state = { failed: false }; }
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error) { this.props.onFail?.(error); }
  render() { return this.state.failed ? null : this.props.children; }
}

export default function RoomDrawingPane({
  project, projectId, room, facts = [], activeFactKey = null, focusRequest = null, fallback,
}) {
  const { t } = useTranslation();
  const [pdfUrl, setPdfUrl] = useState(null);
  const [pdfState, setPdfState] = useState('loading');        // loading | ready | failed
  const [focus, setFocus] = useState(null);
  const nonce = useRef(0);
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined'
    && window.matchMedia('(max-width: 767px)').matches);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const mq = window.matchMedia('(max-width: 767px)');
    const on = (e) => setIsMobile(e.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);

  // The PDF, once per project.
  useEffect(() => {
    let alive = true;
    let url = null;
    setPdfState('loading');
    getPdfUrl(projectId)
      .then((u) => {
        if (!alive) { if (u) URL.revokeObjectURL(u); return; }
        url = u;
        setPdfUrl(u);
        setPdfState(u ? 'ready' : 'failed');
      })
      .catch(() => { if (alive) setPdfState('failed'); });
    return () => { alive = false; if (url) URL.revokeObjectURL(url); };
  }, [projectId]);

  const sutapdinimas = project?._meta?.geometrija?.sutapdinimas || null;
  const overlay = useMemo(
    () => buildCheckOverlay({ room, facts, sutapdinimas, activeFactKey }),
    [room, facts, sutapdinimas, activeFactKey],
  );
  const check = useMemo(() => ({ pages: overlay.pages }), [overlay.pages]);
  const laneScales = useMemo(() => pageScalesFromLane(laneMastelisOf(project)), [project]);

  const go = (target) => {
    if (!target?.page) return;
    nonce.current += 1;
    setFocus({ page: target.page, rect: target.rect, nonce: nonce.current });
  };

  // A new room → look at it. (Facts arrive a moment after the room changes; the
  // outline is in them, so this waits for the room focus to exist.)
  const roomKey = room?.nr != null ? String(room.nr) : null;
  // …and look again when the SAME room's place changes — a free re-read or a corrected
  // outline gives it a new frame; a fixed height or floor covering does not.
  const focusKey = roomKey && overlay.roomFocus
    ? `${roomKey}|${overlay.roomFocus.page}|${(overlay.roomFocus.rect || []).join(',')}` : null;
  const focusedFor = useRef(null);
  useEffect(() => {
    if (!focusKey || focusedFor.current === focusKey) return;
    focusedFor.current = focusKey;
    go(overlay.roomFocus);
    // `go` is recreated every render — the room and its focus are what this waits for
  }, [focusKey]);

  // „Rodyti brėžinyje" on a fact → its own place, else the room.
  const requestNonce = focusRequest?.nonce;
  useEffect(() => {
    if (!focusRequest?.key) return;
    const o = buildCheckOverlay({ room, facts, sutapdinimas, activeFactKey: focusRequest.key });
    go(o.factFocus || o.roomFocus);
    // a request is its nonce — the same fact asked for twice is two requests
  }, [requestNonce]);

  if (isMobile || pdfState === 'failed') {
    return (
      <div className="flex min-w-0 flex-col gap-2">
        {pdfState === 'failed' && !isMobile && (
          <p className="text-[13px] text-muted-foreground">{t('project.roomSheet.drawFallback')}</p>
        )}
        <RoomPlanPane {...fallback} />
      </div>
    );
  }

  const states = new Set(Object.values(overlay.pages).flatMap((p) => p.walls.map((w) => w.state)));
  const hasStrings = Object.values(overlay.pages).some((p) => p.strings.length > 0);
  const hasOpenings = Object.values(overlay.pages).some((p) => p.openings.length > 0);
  const space = Object.values(overlay.pages).find((p) => p.openSpace)?.openSpace || null;
  const others = space ? space.nariai.filter((n) => n !== roomKey) : [];
  const reason = cleanUserText(overlay.outlineReason || '');
  const noOutline = !space && !Object.values(overlay.pages).some((p) => p.outline);

  return (
    <div className="flex min-w-0 flex-col gap-2" data-testid="room-drawing-pane">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[13px] text-muted-foreground">
          {t('project.roomSheet.drawCaption', { room: roomKey ?? '' })}
        </p>
        <div className="flex items-center gap-2">
          <button type="button" className={BTN} disabled={!overlay.roomFocus} onClick={() => go(overlay.roomFocus)}>
            <ScanSearch className="h-4 w-4" aria-hidden="true" />
            {t('project.roomSheet.drawToRoom')}
          </button>
          <button
            type="button"
            className={BTN}
            disabled={!overlay.roomFocus}
            onClick={() => go({ page: focus?.page || overlay.roomFocus?.page, rect: [0, 0, 1, 1] })}
          >
            <Maximize2 className="h-4 w-4" aria-hidden="true" />
            {t('project.roomSheet.drawWholeSheet')}
          </button>
        </div>
      </div>

      <div className="h-[68vh] min-h-[460px] overflow-hidden rounded-[2px] border border-border bg-card">
        {pdfState === 'ready' && pdfUrl ? (
          <ViewerBoundary onFail={() => setPdfState('failed')}>
            <TakeoffViewer
              fileUrl={pdfUrl}
              projectId={projectId}
              rooms={[]}
              check={check}
              focus={focus}
              laneScales={laneScales}
            />
          </ViewerBoundary>
        ) : (
          <p className="p-4 text-[14px] text-muted-foreground">{t('project.roomSheet.drawLoading')}</p>
        )}
      </div>

      {space && (
        <p className="text-[13px] leading-snug text-[hsl(var(--ink-2))]">
          {t('project.roomSheet.drawOpenSpace', { rooms: others.join(', ') })}
        </p>
      )}
      {noOutline && (
        <p className="text-[13px] leading-snug text-[hsl(var(--ink-2))]">
          {reason
            ? t('project.roomSheet.drawNoOutline', { reason: reason.replace(/\.$/, '') })
            : t('project.roomSheet.drawNoOutlinePlain')}
        </p>
      )}
      {(states.size > 0 || hasOpenings) && (
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-muted-foreground">
          <li className="font-semibold uppercase tracking-wide">{t('project.roomSheet.legendWallsTitle')}</li>
          {WALL_LEGEND.filter(([state]) => states.has(state)).map(([state, colour, dash, key]) => (
            <li key={state} className="flex items-center gap-1.5">
              <svg width="22" height="8" aria-hidden="true">
                <line x1="1" y1="4" x2="21" y2="4" stroke={colour} strokeWidth="3.5" strokeLinecap="round" strokeDasharray={dash || undefined} />
              </svg>
              {t(`project.roomSheet.${key}`)}
            </li>
          ))}
          {hasStrings && (
            <li className="flex items-center gap-1.5">
              <svg width="22" height="8" aria-hidden="true">
                <line x1="1" y1="4" x2="21" y2="4" stroke="#15803d" strokeOpacity="0.55" strokeWidth="6" strokeLinecap="round" />
              </svg>
              {t('project.roomSheet.legendStrings')}
            </li>
          )}
          {hasOpenings && (
            <li className="flex items-center gap-1.5">
              <svg width="22" height="8" aria-hidden="true">
                <line x1="2" y1="4" x2="20" y2="4" stroke="#7c3aed" strokeWidth="4.5" strokeLinecap="round" />
              </svg>
              {t('project.roomSheet.legendOpenings')}
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
