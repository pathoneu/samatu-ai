/**
 * PatikraEntry — step 2 of the project opens on the QUESTIONS (pages/PatikraQuestions.jsx): the short list of
 * what the drawing did not say, each with the program's proposal. The room-by-room sheet (pages/RoomSheet.jsx)
 * is the secondary view: it shows when a room (`?kambarys=`) or the project-wide stage (`?etapas=`) is asked
 * for — the links every screen of Patikra already uses.
 */

import { useSearchParams } from 'react-router';

import PatikraQuestions from '@/pages/PatikraQuestions';
import RoomSheet from '@/pages/RoomSheet';

export default function PatikraEntry() {
  const [params] = useSearchParams();
  return params.has('kambarys') || params.has('etapas') ? <RoomSheet /> : <PatikraQuestions />;
}
