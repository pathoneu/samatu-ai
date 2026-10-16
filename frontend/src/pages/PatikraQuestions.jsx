/**
 * PatikraQuestions — Patikra opens with a short list of QUESTIONS for the whole project.
 *
 * Founder, 2026-09-21, after walking a real project on the room sheet: „viskas pasižymi labai gerai ir tiksliai…
 * bet per daug veiksmų visokių būtų rangovui". Measured on that project: 66 facts on screen, 22 of them wait for
 * a person — three kinds of question. So: ONE pattern for everything —
 *
 *     klausimas → programos siūlomas atsakymas → „Tinka" (arba pataisyti) → kas pasikeitė → kitas klausimas
 *
 * — a question of one kind is asked ONCE for the whole project, what was read from the drawing stays silent, and
 * the room-by-room sheet (pages/RoomSheet.jsx) is one click away as the secondary view.
 *
 * The list comes from the server (`/api/projects/{id}/questions`: the very facts the room sheet shows, grouped)
 * and is asked for again after every answer — an answer settles other questions (a room he points at gets its
 * walls read and leaves the perimeter list by itself). Answers go down the write paths the room sheet uses
 * (lib/questions.js builds them, lib/useProjectFixes lands them): one recompute, what moved in the sąmata shown
 * above the NEXT question — no extra „Toliau" click — and one undo.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { useTranslation } from 'react-i18next';
import { ArrowRight, Check, CircleHelp, Loader2, MinusCircle, PenLine } from 'lucide-react';

import { getProject, logCorrection, refreshProjectFromBackend } from '@/lib/projectStore';
import { questionCorrection, questionVerdict } from '@/lib/learningEvents';
import { useProjectFixes } from '@/lib/useProjectFixes';
import {
  answerSummary, doorsAnswer, floorAnswer, heightAnswer, nextOpenQuestion, numbersAnswer, openingsAnswer, progressOf,
  questionAfterAnswer, wallsAnswer,
} from '@/lib/questions';
import { fetchQuestions } from '@/lib/questionsApi';
import { fetchRoomFacts, saveAssumptionEdit, saveRoomEdit } from '@/lib/roomSheetApi';
import { fetchOutlineAt, fetchSplitProposal, fetchSplitSpace } from '@/lib/roomOutlineApi';
import { nextSplitClick, outlineFailureKey, roomsWithOutline, roomsWithSplit, splitFailureKey } from '@/lib/roomOutline';
import { orderFacts, roomsInDrawingOrder } from '@/lib/roomSheet';
import { ltNumber } from '@/lib/ledger';
import { ltPlural } from '@/lib/ltPlural';
import { cleanUserText } from '@/lib/userText';
import { pilotSession, recordPilot, releasePilotSession } from '@/lib/telemetry';
import { StepBar } from '@/pages/InteriorProject';
import FreeRereadBanner from '@/components/project/FreeRereadBanner';
import RoomDrawingPane from '@/components/roomsheet/RoomDrawingPane';
import FixConsequence from '@/components/roomsheet/FixConsequence';
import {
  ChoicesBody, NumberAllBody, NumbersBody, OpeningsBody, OutlineBody, Q_PLAIN, Q_PRIMARY,
} from '@/components/questions/QuestionBodies';

// which of the room's facts a question is about — what the drawing lights up
const FACT_OF = {
  aukstis: 'aukstis', konturas: 'perimetras', erdve: 'perimetras', perimetras: 'perimetras', plotas: 'plotas',
  angos: 'angos', grindys: 'grindys', apdaila: 'apdaila',
};
const WITH_DRAWING = new Set(['outline', 'split', 'numbers', 'choices', 'openings']);
// questions whose evidence is on ANOTHER sheet than the room's outline (the floor plan, the area label): the
// drawing goes to that fact's own place instead of the room
const OWN_PLACE = new Set(['grindys', 'plotas']);

export default function PatikraQuestions() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();

  const [project, setProject] = useState(() => getProject(id));
  const [pulled, setPulled] = useState(false);
  const [data, setData] = useState(null);                       // {questions, asked, read, rooms}
  const [loadState, setLoadState] = useState('loading');       // loading | ready | failed
  const [currentId, setCurrentId] = useState(null);
  const [skipped, setSkipped] = useState(() => new Set());
  const [answered, setAnswered] = useState(0);
  const [focusNr, setFocusNr] = useState(null);                // the room the drawing shows
  const [roomFacts, setRoomFacts] = useState(null);
  const [factsNonce, setFactsNonce] = useState(0);
  const [focusRequest, setFocusRequest] = useState(null);     // {key, nonce} — the drawing jumps to that fact's own place
  // a shared space: the program's proposal, or a line he draws himself
  const [proposal, setProposal] = useState(null);              // null | 'loading' | the api answer
  const [drawing, setDrawing] = useState(false);
  const [splitFirst, setSplitFirst] = useState(null);
  const [pickNotice, setPickNotice] = useState(null);         // why the last click on the drawing did not work
  // a click in a NEIGHBOUR's room from a room whose walls close only a pocket (2026-09-23): the server proposes
  // the boundary through the two rooms' joined space — `join` is that answer (+ the click), shown until „Tinka"
  // or a line he draws himself (`joinDrawing`)
  const [join, setJoin] = useState(null);
  const [joinDrawing, setJoinDrawing] = useState(false);

  const skippedRef = useRef(skipped);
  skippedRef.current = skipped;
  const standAfter = useRef(null);                             // {id, index} — where to stand once the list is rebuilt
  const topRef = useRef(null);
  const reqRef = useRef(0);

  useEffect(() => {
    if (pulled || !id) return;
    setPulled(true);
    refreshProjectFromBackend(id).then((fresh) => { if (fresh) setProject(fresh); });
  }, [pulled, id]);

  useEffect(() => {
    pilotSession(id);
    return () => { releasePilotSession(id); };
  }, [id]);
  const pilot = useCallback((type, target = {}) => recordPilot(id, type, target), [id]);

  const loadQuestions = useCallback(() => {
    if (!id) return Promise.resolve();
    const req = ++reqRef.current;
    return fetchQuestions(id)
      .then((next) => {
        if (req !== reqRef.current) return;
        const list = next?.questions || [];
        setData(next);
        setLoadState('ready');
        setFactsNonce((n) => n + 1);
        setCurrentId((cur) => {
          const stand = standAfter.current;
          standAfter.current = null;
          if (stand) {
            // an answer changes the whole screen — what it moved is at the top, and so is the next question
            topRef.current?.scrollIntoView({ block: 'start' });
            return questionAfterAnswer(list, skippedRef.current, stand.id, stand.index)?.id ?? null;
          }
          if (cur && list.some((q) => q.id === cur)) return cur;
          return nextOpenQuestion(list, skippedRef.current)?.id ?? null;
        });
      })
      .catch((err) => {
        if (req !== reqRef.current) return;
        console.error('[klausimai] load failed:', err);
        setLoadState('failed');
      });
  }, [id]);

  useEffect(() => { loadQuestions(); }, [loadQuestions]);

  const {
    busy, run, land, undoLastFix, lastFix,
  } = useProjectFixes({
    project, setProject, t, afterLand: loadQuestions,
    onUndo: (fix) => {
      pilot('question_undo', { kind: 'question', id: fix.factKey });
      standAfter.current = { id: fix.factKey, index: 0 };      // the undone question is asked again — stand on it
      setAnswered((n) => Math.max(0, n - 1));
    },
  });

  const questions = useMemo(() => data?.questions || [], [data]);
  const current = questions.find((q) => q.id === currentId) || null;
  const progress = progressOf(questions, skipped, answered);

  // ── the room the drawing shows ─────────────────────────────────────────────────────────────────────
  // outline questions walk their rooms one after another; everything else starts on its first room
  const [outlineSkips, setOutlineSkips] = useState(() => new Set());
  const outlineItem = current?.answer === 'outline'
    ? (current.items.find((i) => !outlineSkips.has(i.room_nr)) || null) : null;

  useEffect(() => {
    if (!current) { setFocusNr(null); return; }
    if (current.answer === 'outline') { setFocusNr(outlineItem?.room_nr ?? null); return; }
    // …or, when nothing can be answered with one click, on the first room he is asked to look at himself
    const shown = [...current.items, ...(current.manual || [])];
    setFocusNr((cur) => (cur && shown.some((i) => i.room_nr === cur) ? cur : (shown[0]?.room_nr ?? null)));
    // a new question (or a rebuilt one) decides the room; clicks inside it move `focusNr` themselves
  }, [current?.id, current?.items?.length, current?.manual?.length, outlineItem?.room_nr]);

  useEffect(() => {
    if (!id || !focusNr || !current || !WITH_DRAWING.has(current.answer)) { setRoomFacts(null); return undefined; }
    let alive = true;
    fetchRoomFacts(id, focusNr)
      .then((facts) => {
        if (!alive) return;
        setRoomFacts(facts);
        if (OWN_PLACE.has(current.kind)) setFocusRequest((cur) => ({ key: FACT_OF[current.kind], nonce: (cur?.nonce || 0) + 1 }));
      })
      .catch(() => { if (alive) setRoomFacts(null); });
    return () => { alive = false; };
    // `factsNonce` moves after every answer: the room's outline and walls may be new
  }, [id, focusNr, current?.answer, factsNonce]);

  // ── a shared space: ask the program for its boundary as soon as the question is in front of him ────
  useEffect(() => { setPickNotice(null); setJoin(null); setJoinDrawing(false); setSplitFirst(null); }, [currentId, focusNr]);

  useEffect(() => {
    setDrawing(false);
    setSplitFirst(null);
    if (current?.answer !== 'split') { setProposal(null); return undefined; }
    let alive = true;
    setProposal('loading');
    fetchSplitProposal(id, current.items[0].room_nr)
      .then((answer) => {
        if (!alive) return;
        setProposal(answer);
        if (answer?.status !== 'ok') setDrawing(true);         // nothing to propose → he draws it
      })
      .catch(() => { if (alive) { setProposal({ status: 'failed' }); setDrawing(true); } });
    return () => { alive = false; };
  }, [id, current?.id, current?.answer]);

  // ── answers ────────────────────────────────────────────────────────────────────────────────────────
  // the learning journal (togal-v2 W11): „Tinka" = the program's proposal taken, otherwise his own answer
  const remember = useCallback((question, payload, how, touched) => {
    const ev = questionCorrection(question, questionVerdict(question, payload, how), touched);
    if (ev && id) logCorrection(id, ev);
  }, [id]);

  const answer = useCallback((question, built, send, landOptions = {}) => run(async () => {
    if (!built) return;
    const { learn = null, ...opts } = landOptions;
    pilot('question_answer', { kind: 'question', id: question.kind });
    standAfter.current = { id: question.id, index: Math.max(0, questions.findIndex((q) => q.id === question.id)) };
    const result = await send(built);
    remember(question, learn?.payload, learn?.how, built.touched);
    setAnswered((n) => n + 1);
    const summary = answerSummary(question, built, t);
    await land(result, { ...opts, factKey: question.id, sameValue: Boolean(built.sameValue), summary });
  }), [run, pilot, questions, land, t, remember]);

  // the way without a click: the wall length typed by hand goes down the perimeter's own write path
  const typeOutlineLength = useCallback((value) => {
    if (!current || !outlineItem) return;
    const nr = outlineItem.room_nr;
    const built = numbersAnswer(project, [{ room_nr: nr, field: 'perimetras_m', proposed: null }], { [nr]: value });
    answer(current, built && { ...built, typed: true, value: Number(value) }, (a) => saveRoomEdit(project, a.rooms), { fromInterior: true, learn: { how: 'own' } });
  }, [current, outlineItem, project, answer]);

  const onBodyAnswer = (payload) => {
    const q = current;
    if (!q) return;
    if (q.answer === 'number_all') {
      answer(q, heightAnswer(project, q.items, payload.value, payload.perRoom),
        (a) => saveAssumptionEdit(project, 'lubu_auksciai', a.table), { learn: { payload } });
    } else if (q.answer === 'numbers') {
      answer(q, numbersAnswer(project, q.items, payload.values), (a) => saveRoomEdit(project, a.rooms), { fromInterior: true, learn: { payload } });
    } else if (q.answer === 'choices' && q.kind === 'apdaila') {
      answer(q, wallsAnswer(project, q.items, payload.values), (a) => saveAssumptionEdit(project, 'walls_paint_override', a.table), { learn: { payload } });
    } else if (q.answer === 'choices' && q.kind === 'durys') {
      // one choice for the whole project — the frameless-door assumption, down the Prielaidos write path
      // „su apvadais" takes the frameless-door row away on purpose — not an orphan to carry back
      answer(q, doorsAnswer(project, q.items, payload.values), (a) => saveAssumptionEdit(project, 'vidaus_durys_beapvadines', a.value), { scopeChange: true, learn: { payload } });
    } else if (q.answer === 'choices') {
      answer(q, floorAnswer(project, q.items, payload.values), (a) => saveRoomEdit(project, a.rooms), { fromInterior: true, learn: { payload } });
    } else if (q.answer === 'openings') {
      answer(q, openingsAnswer(project, q.items, payload.picked, payload.edits), (a) => saveRoomEdit(project, a.rooms), { fromInterior: true, learn: { payload } });
    }
  };

  // „Parodyti patalpą": one click inside the room → its wall-exact outline, walls read again
  // an outline the server found for a click (or for „Tinka" on the proposed one) lands on the project — or, when
  // the click may not become an outline, the reason is said at the drawing
  const landOutline = useCallback(async (nr, found, { accepted = false, point = null } = {}) => {
    if (found?.status === 'shared') {
      // the place is a neighbour's, and this room's pocket joins it: the boundary is proposed, not landed
      setPickNotice(null);
      setJoin({ ...found, point });
      setJoinDrawing(false);
      return;
    }
    const joined = Boolean(found?.rooms && !found?.room);      // „Tinka" on a joined space: BOTH rooms come back
    const rooms = joined ? roomsWithSplit(project, found) : roomsWithOutline(project, nr, found);
    if (!rooms) {
      const { key, params } = outlineFailureKey(found);
      setPickNotice(t(`project.roomSheet.${key}`, params));
      return;
    }
    setPickNotice(null);
    setJoin(null);
    pilot('question_answer', { kind: 'question', id: current.kind });
    standAfter.current = { id: current.id, index: Math.max(0, questions.findIndex((q) => q.id === current.id)) };
    setAnswered((n) => n + 1);
    const touched = joined ? Object.keys(found.rooms || {}) : [nr];
    // the server's „konturas" row (outline-at, with this question's id) is this answer's journal record
    await land(await saveRoomEdit(project, rooms), {
      fromInterior: true, factKey: current.id, summary: answerSummary(current, { touched, accepted, joined }, t),
    });
  }, [project, current, questions, land, pilot, t]);

  const pickOutline = useCallback((point) => run(async () => {
    if (!point || !current || !outlineItem) return;
    await landOutline(outlineItem.room_nr, await fetchOutlineAt(id, outlineItem.room_nr, point, { klausimas: current.id }), { point });
  }), [run, current, outlineItem, id, landOutline]);

  // „Tinka" on the boundary proposed after a click in the neighbour's room: the same click, labelled
  const acceptJoin = useCallback(() => run(async () => {
    if (!current || !outlineItem || !join?.point) return;
    await landOutline(outlineItem.room_nr, await fetchOutlineAt(id, outlineItem.room_nr, join.point, { pritarta: true, klausimas: current.id }), { accepted: true });
  }), [run, current, outlineItem, id, join, landOutline]);

  // „Nubrėšiu pats" after such a click: two clicks cut the JOINED space along his line
  const pickJoinSplit = useCallback((point) => {
    const { first, request } = nextSplitClick(splitFirst, point);
    setSplitFirst(first);
    if (!request || !current || !outlineItem || !join?.su) return;
    run(async () => {
      const found = await fetchSplitSpace(id, outlineItem.room_nr, { ...request, su: join.su }, { klausimas: current.id });
      const rooms = roomsWithSplit(project, found);
      if (!rooms) {
        const { key, params } = splitFailureKey(found);
        setPickNotice(t(`project.roomSheet.${key}`, params));
        return;
      }
      setPickNotice(null);
      setJoin(null);
      setJoinDrawing(false);
      pilot('question_answer', { kind: 'question', id: current.kind });
      standAfter.current = { id: current.id, index: Math.max(0, questions.findIndex((q) => q.id === current.id)) };
      setAnswered((n) => n + 1);
      // recorded by the server's „konturas" rows (split-space, with this question's id)
      await land(await saveRoomEdit(project, rooms), {
        fromInterior: true, factKey: current.id, summary: answerSummary(current, { touched: Object.keys(found.rooms || {}), joined: true }, t),
      });
    });
  }, [splitFirst, current, outlineItem, join, run, id, project, questions, land, pilot, t]);

  // „Tinka" on the outline the program proposed (2026-09-23): the same click, at a point inside that outline
  const acceptOutline = useCallback(() => run(async () => {
    const cand = outlineItem?.proposed_outline;
    if (!current || !outlineItem || !Array.isArray(cand?.taskas_pct)) return;
    const point = { page: cand.page, x_pct: cand.taskas_pct[0], y_pct: cand.taskas_pct[1] };
    await landOutline(outlineItem.room_nr, await fetchOutlineAt(id, outlineItem.room_nr, point, { pritarta: true, klausimas: current.id }), { accepted: true });
  }), [run, current, outlineItem, id, landOutline]);

  const landSplit = useCallback(async (found, how = 'own') => {
    const rooms = roomsWithSplit(project, found);
    if (!rooms) {
      const { key, params } = splitFailureKey(found);
      setPickNotice(t(`project.roomSheet.${key}`, params));
      return;
    }
    setPickNotice(null);
    pilot('question_answer', { kind: 'question', id: 'erdve' });
    standAfter.current = { id: current.id, index: Math.max(0, questions.findIndex((q) => q.id === current.id)) };
    setAnswered((n) => n + 1);
    const saved = await saveRoomEdit(project, rooms);
    // a line he drew went through split-space, whose „konturas" rows are the record; the program's proposal
    // (split-proposal) wrote nothing on the server, so its „Tinka" is recorded here — one act, one row
    if (how === 'accepted') remember(current, null, how, Object.keys(found.rooms || {}));
    await land(saved, {
      fromInterior: true, factKey: current.id, summary: answerSummary(current, { touched: Object.keys(found.rooms || {}) }, t),
    });
  }, [project, current, questions, land, pilot, t, remember]);

  const pickSplit = useCallback((point) => {
    const { first, request } = nextSplitClick(splitFirst, point);
    setSplitFirst(first);
    if (!request || !current) return;
    run(async () => { await landSplit(await fetchSplitSpace(id, current.items[0].room_nr, request, { klausimas: current.id })); });
  }, [splitFirst, current, run, landSplit, id]);

  const skip = useCallback(() => {
    if (!current) return;
    pilot('question_skip', { kind: 'question', id: current.kind });
    const next = new Set(skipped).add(current.id);
    setSkipped(next);
    setCurrentId(nextOpenQuestion(questions, next, current.id)?.id ?? null);
  }, [current, skipped, questions, pilot]);

  const firstRoomNr = useMemo(() => {
    const rooms = roomsInDrawingOrder(project);
    return rooms[0]?.nr != null ? String(rooms[0].nr) : null;
  }, [project]);
  const openRoom = (nr) => navigate(`/project/${id}/patikra?kambarys=${encodeURIComponent(nr)}`);

  // ── render ─────────────────────────────────────────────────────────────────────────────────────────
  if (!project) {
    return <p className="p-8 text-[16px] text-muted-foreground">{pulled ? t('project.roomSheet.notFound') : t('project.roomSheet.loading')}</p>;
  }

  const left = progress.open;
  const leftWord = ltPlural(left, t('project.questions.nounOne'), t('project.questions.nounFew'), t('project.questions.nounMany'));
  const factList = orderFacts(roomFacts?.facts);
  const showDrawing = Boolean(current && WITH_DRAWING.has(current.answer) && roomFacts?.room && String(roomFacts.room.nr) === String(focusNr));
  const proposed = proposal && proposal !== 'loading' && proposal.status === 'ok' ? proposal : null;
  const pick = current?.answer === 'outline' && join && joinDrawing
    ? {
      active: true, mode: 'split', first: splitFirst, busy, notice: pickNotice,
      text: { hint: t(splitFirst ? 'project.roomSheet.splitHintSecond' : 'project.roomSheet.splitHintFirst', { rooms: [outlineItem?.room_nr, join.su].filter(Boolean).join(', ') }), why: t('project.roomSheet.splitHintWhy') },
      onStart: () => {}, onCancel: () => { setSplitFirst(null); setJoinDrawing(false); }, onPoint: pickJoinSplit,
    }
    : current?.answer === 'outline'
    ? {
      active: Boolean(outlineItem) && !join, mode: 'outline', first: null, busy, notice: pickNotice,
      // with a proposal on the drawing the banner says so — „Tinka" is on the left, a click elsewhere replaces it
      text: outlineItem?.proposed_outline
        ? { hint: t('project.roomSheet.outlinePickHintProposal', { room: outlineItem.room_nr }), why: t('project.roomSheet.outlinePickWhyProposal') }
        : null,
      onStart: () => {}, onCancel: () => setOutlineSkips((s) => new Set(s).add(outlineItem?.room_nr)), onPoint: pickOutline,
    }
    : current?.answer === 'split' && drawing
      ? { active: true, mode: 'split', first: splitFirst, busy, notice: pickNotice, onStart: () => {}, onCancel: () => { setSplitFirst(null); if (proposed) setDrawing(false); }, onPoint: pickSplit }
      : null;

  return (
    <div ref={topRef} className="flex min-h-full flex-col bg-background text-[16px]" data-testid="patikra-questions">
      <StepBar
        step="patikra"
        hasPdf
        projectId={id}
        setStep={(s) => navigate(s === 'patikra' ? `/project/${id}/patikra` : `/project/${id}?step=${s}`)}
      />

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 bg-[hsl(var(--primary))] px-4 py-3 text-white">
        <div className="min-w-0 flex-1">
          <h1 className="text-[18px] font-semibold leading-snug">
            {loadState !== 'ready'
              ? t('project.questions.title')
              : left > 0
                ? t('project.questions.headOpen', { count: left, word: leftWord })
                : t(progress.skipped > 0 ? 'project.questions.headSkipped' : 'project.questions.headDone')}
          </h1>
          <p className="text-[14px] text-white/80">{t('project.questions.headSub')}</p>
        </div>
        {firstRoomNr && (
          <button
            type="button"
            onClick={() => openRoom(firstRoomNr)}
            className="inline-flex min-h-[44px] items-center gap-1.5 rounded-[2px] border border-white/25 px-3 text-[14px] font-semibold text-white/90 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
          >
            {t('project.questions.byRooms')}
          </button>
        )}
      </div>

      <FreeRereadBanner project={project} className="mx-4 mt-3" onComplete={(next) => { setProject(next); loadQuestions(); }} />

      {/* what the LAST answer moved — above the next question, with the way back */}
      {lastFix && (
        <div className="mx-4 mt-3 rounded-[2px] border border-border bg-card pt-2" data-testid="question-answered">
          {lastFix.summary && <p className="px-4 pb-2 text-[15px] font-semibold text-foreground">{lastFix.summary}</p>}
          <FixConsequence consequence={lastFix.consequence} busy={busy} onUndo={undoLastFix} />
        </div>
      )}

      <div className="flex flex-1 flex-col gap-4 p-4 lg:flex-row lg:items-start">
        {/* the questions, top to bottom in the order that lets one answer settle the next */}
        <nav className="w-full shrink-0 lg:w-[300px]" aria-label={t('project.questions.title')}>
          <ol className="flex flex-col gap-1.5">
            {questions.map((q, i) => {
              const isCurrent = q.id === currentId;
              const isSkipped = skipped.has(q.id);
              return (
                <li key={q.id}>
                  <button
                    type="button"
                    onClick={() => setCurrentId(q.id)}
                    aria-current={isCurrent ? 'step' : undefined}
                    className={`flex w-full items-start gap-2 rounded-[2px] border px-3 py-2.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
                      ${isCurrent ? 'border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2)/0.08)]' : 'border-border bg-card hover:bg-muted'}`}
                    data-testid={`question-rail-${q.id}`}
                  >
                    {isSkipped
                      ? <MinusCircle className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                      : <CircleHelp className="mt-0.5 h-5 w-5 shrink-0 text-[hsl(var(--conf-med))]" aria-hidden="true" />}
                    <span className="min-w-0">
                      <span className="block text-[12px] font-mono text-muted-foreground">
                        {t('project.questions.step', { index: i + 1, total: questions.length })}
                        {isSkipped ? ` · ${t('project.questions.skippedMark')}` : ''}
                      </span>
                      <span className="block text-[15px] font-semibold leading-snug text-foreground">{cleanUserText(q.title)}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
          {loadState === 'ready' && data && (
            <p className="mt-3 flex items-start gap-2 text-[13px] leading-snug text-[hsl(var(--ink-2))]">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--accent-2))]" aria-hidden="true" />
              {t('project.questions.readNote', { read: data.read, total: data.read + data.asked, count: data.rooms })}
            </p>
          )}
        </nav>

        <div className="min-w-0 flex-1">
          {loadState === 'loading' && (
            <p className="flex items-center gap-2 p-4 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              {t('project.questions.loading')}
            </p>
          )}
          {loadState === 'failed' && (
            <div className="rounded-[2px] border border-border bg-card p-4">
              <p className="text-[15px]">{t('project.questions.loadError')}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" className={Q_PLAIN} onClick={() => { setLoadState('loading'); loadQuestions(); }}>{t('project.questions.retry')}</button>
                {firstRoomNr && <button type="button" className={Q_PLAIN} onClick={() => openRoom(firstRoomNr)}>{t('project.questions.byRooms')}</button>}
              </div>
            </div>
          )}

          {loadState === 'ready' && !current && (
            <div className="rounded-[2px] border border-border bg-card p-5" data-testid="questions-done">
              <h2 className="text-[20px] font-semibold">
                {t(questions.length === 0 ? 'project.questions.doneTitle' : 'project.questions.doneSkippedTitle')}
              </h2>
              <p className="mt-1 max-w-[60ch] text-[15px] leading-relaxed text-[hsl(var(--ink-2))]">
                {questions.length === 0 ? t('project.questions.doneBody') : t('project.questions.doneSkipped', { count: progress.skipped })}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <button type="button" className={Q_PRIMARY} onClick={() => navigate(`/project/${id}?step=samata`)}>
                  {t('project.questions.toEstimate')}
                  <ArrowRight className="h-5 w-5" aria-hidden="true" />
                </button>
                {firstRoomNr && <button type="button" className={Q_PLAIN} onClick={() => openRoom(firstRoomNr)}>{t('project.questions.byRooms')}</button>}
                <button type="button" className={Q_PLAIN} onClick={() => navigate(`/project/${id}/patikra?etapas=bendri`)}>{t('project.questions.general')}</button>
              </div>
            </div>
          )}

          {loadState === 'ready' && current && (
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start">
              <section
                className={`min-w-0 rounded-[2px] border border-border bg-card p-4 ${WITH_DRAWING.has(current.answer) ? (current.answer === 'choices' ? 'xl:w-[540px] xl:shrink-0' : 'xl:w-[440px] xl:shrink-0') : 'max-w-[760px] flex-1'}`}
                data-testid={`question-card-${current.id}`}
              >
                <h2 className="text-[20px] font-semibold leading-snug">{cleanUserText(current.title)}</h2>
                <p className="mt-1 text-[15px] leading-relaxed text-[hsl(var(--ink-2))]">{cleanUserText(current.why)}</p>

                <div className="mt-4">
                  {current.answer === 'number_all' && <NumberAllBody question={current} busy={busy} onAnswer={onBodyAnswer} />}
                  {current.answer === 'numbers' && <NumbersBody question={current} busy={busy} focusNr={focusNr} onFocus={setFocusNr} onAnswer={onBodyAnswer} />}
                  {current.answer === 'choices' && <ChoicesBody question={current} busy={busy} focusNr={focusNr} onFocus={setFocusNr} onAnswer={onBodyAnswer} />}
                  {current.answer === 'openings' && <OpeningsBody question={current} busy={busy} focusNr={focusNr} onFocus={setFocusNr} onAnswer={onBodyAnswer} onOpenRoom={openRoom} />}

                  {current.answer === 'outline' && !join && (
                    <OutlineBody question={current} item={outlineItem} busy={busy} onAccept={acceptOutline} onTypeLength={typeOutlineLength} />
                  )}
                  {current.answer === 'outline' && join && outlineItem && (
                    <div className="flex flex-col gap-3" data-testid="outline-join">
                      <p className="text-[15px] font-semibold">
                        <span className="font-mono text-muted-foreground">{outlineItem.room_nr}</span> {outlineItem.room_name}
                      </p>
                      <p className="text-[14px] leading-snug text-[hsl(var(--ink-2))]">
                        {t('project.questions.outlineSharedWith', {
                          nr: outlineItem.room_nr, su: join.su,
                          a: ltNumber(Number(join.rooms?.[outlineItem.room_nr]?.plotas_m2), 2), tableA: ltNumber(Number(join.rooms?.[outlineItem.room_nr]?.plotas_uzrasas_m2), 2),
                          b: ltNumber(Number(join.rooms?.[join.su]?.plotas_m2), 2), tableB: ltNumber(Number(join.rooms?.[join.su]?.plotas_uzrasas_m2), 2),
                        })}
                      </p>
                      {!joinDrawing ? (
                        <div className="flex flex-wrap gap-2">
                          <button type="button" className={Q_PRIMARY} disabled={busy} data-testid="question-accept" onClick={acceptJoin}>
                            <Check className="h-4 w-4" aria-hidden="true" />
                            {t('project.questions.accept')}
                          </button>
                          <button type="button" className={Q_PLAIN} disabled={busy} onClick={() => { setJoinDrawing(true); setSplitFirst(null); }}>
                            <PenLine className="h-4 w-4" aria-hidden="true" />
                            {t('project.questions.splitDraw')}
                          </button>
                          <button type="button" className={Q_PLAIN} disabled={busy} onClick={() => setJoin(null)}>
                            {t('project.questions.outlineJoinBack')}
                          </button>
                        </div>
                      ) : (
                        <p className="text-[14px] leading-snug text-[hsl(var(--ink-2))]">{t('project.questions.splitDrawing')}</p>
                      )}
                    </div>
                  )}

                  {current.answer === 'split' && (
                    <div className="flex flex-col gap-3">
                      {proposal === 'loading' && (
                        <p className="flex items-center gap-2 text-[15px] text-muted-foreground">
                          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                          {t('project.questions.splitLoading')}
                        </p>
                      )}
                      {proposed && !drawing && (
                        <>
                          <ul className="rounded-[2px] border border-border">
                            {current.items.map((item) => {
                              const k = proposed.rooms?.[item.room_nr]?._konturas || {};
                              return (
                                <li key={item.room_nr} className="flex flex-wrap items-baseline justify-between gap-x-3 border-t border-border px-3 py-2 first:border-t-0">
                                  <span className="text-[15px] font-semibold"><span className="font-mono text-muted-foreground">{item.room_nr}</span> {item.room_name}</span>
                                  <span className="font-mono text-[14px] text-[hsl(var(--ink-2))]">
                                    {t('project.questions.splitArea', { area: ltNumber(k.plotas_m2, 2), table: ltNumber(k.plotas_uzrasas_m2, 2) })}
                                  </span>
                                </li>
                              );
                            })}
                          </ul>
                          <p className="text-[14px] leading-snug text-[hsl(var(--ink-2))]">
                            {t(proposed.pagal === 'kampas' ? 'project.questions.splitByCorner' : 'project.questions.splitByAreas')}
                          </p>
                          <div className="flex flex-wrap gap-2">
                            <button type="button" className={Q_PRIMARY} disabled={busy} data-testid="question-accept" onClick={() => run(() => landSplit(proposed, 'accepted'))}>
                              <Check className="h-4 w-4" aria-hidden="true" />
                              {t('project.questions.accept')}
                            </button>
                            <button type="button" className={Q_PLAIN} disabled={busy} onClick={() => setDrawing(true)}>
                              <PenLine className="h-4 w-4" aria-hidden="true" />
                              {t('project.questions.splitDraw')}
                            </button>
                          </div>
                        </>
                      )}
                      {drawing && (
                        <p className="text-[14px] leading-snug text-[hsl(var(--ink-2))]">
                          {proposed ? t('project.questions.splitDrawing') : t('project.questions.splitNoProposal')}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                <div className="mt-4 border-t border-border pt-3">
                  <button type="button" className={`${Q_PLAIN} min-h-[36px] px-3 text-[14px]`} disabled={busy} onClick={skip} data-testid="question-skip">
                    {t('project.questions.skip')}
                  </button>
                  <span className="ml-2 text-[13px] text-muted-foreground">{t('project.questions.skipNote')}</span>
                </div>
              </section>

              {WITH_DRAWING.has(current.answer) && (
                <div className="min-w-0 flex-1">
                  {showDrawing ? (
                    <RoomDrawingPane
                      project={project}
                      projectId={id}
                      room={roomFacts.room}
                      facts={factList}
                      activeFactKey={FACT_OF[current.kind] || null}
                      focusRequest={OWN_PLACE.has(current.kind) ? focusRequest : null}
                      pick={pick}
                      hidePickButtons
                      proposal={current.answer === 'split' && proposed && !drawing
                        ? { page: proposed.page, line_pct: proposed.line_pct, rooms: Object.fromEntries(Object.entries(proposed.rooms || {}).map(([nr, r]) => [nr, r.polygon_pct])) }
                        : current.answer === 'outline' && join && !joinDrawing
                          ? { page: join.page, line_pct: join.line_pct, rooms: Object.fromEntries(Object.entries(join.rooms || {}).map(([nr, r]) => [nr, r.polygon_pct])) }
                          : current.answer === 'outline' && outlineItem?.proposed_outline && !join
                            ? { page: outlineItem.proposed_outline.page, line_pct: null, rooms: { [outlineItem.room_nr]: outlineItem.proposed_outline.polygon_pct } }
                            : null}
                      fallback={{ room: roomFacts.room, projectId: id, highlightCorners: false, facts: factList, wholeSheet: true, onToggleWhole: () => {}, activeFactKey: FACT_OF[current.kind] || null }}
                    />
                  ) : (
                    <div className="h-64 animate-pulse rounded-[2px] bg-muted" />
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
