/**
 * ReadRating — „Kaip pavyko perskaityti brėžinį?" 👍 / 👎 plus one optional line, offered once after the paid
 * read (Pathon v3 W5-C, C10 / #170). One row in the corrections journal (source `ivertinimas`), „Atšaukti"
 * takes it back; „Ne dabar" closes it for this project in this browser. Never blocks, no paid call.
 */

import { useState } from 'react';

import Notice from '@/components/ui/Notice';
import FeedbackThumbs from '@/components/ui/FeedbackThumbs';
import { feedbackBody, markReadRated, readRatingDue, sendFeedback } from '@/lib/feedback';

const storage = () => {
  try { return typeof window !== 'undefined' ? window.localStorage : null; } catch { return null; }
};

export default function ReadRating({ project, className = '' }) {
  const [due, setDue] = useState(() => readRatingDue(project, storage()));
  if (!due || !project?.id) return null;
  const close = () => { markReadRated(project.id, storage()); setDue(false); };
  return (
    <Notice tone="info" className={className} onDismiss={close} dismissLabel="Ne dabar" data-testid="read-rating">
      <FeedbackThumbs
        testId="read-rating-thumbs"
        question="Kaip pavyko perskaityti šį brėžinį?"
        upLabel="Gerai"
        downLabel="Blogai"
        linePlaceholder="Kas netiko? (nebūtina)"
        sentText="Įrašyta — ačiū. Tai padeda programai skaityti geriau."
        onSend={async ({ up, line }) => {
          await sendFeedback(project.id, feedbackBody({ kind: 'skaitymas', up, line }));
          markReadRated(project.id, storage());
        }}
        onUndo={() => sendFeedback(project.id, feedbackBody({ kind: 'skaitymas', undo: true }))}
      />
    </Notice>
  );
}
