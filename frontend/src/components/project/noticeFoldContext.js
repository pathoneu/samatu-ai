/**
 * What a NoticeFold tells the notice that leads it (lib/noticeFold LEAD_NOTICES): which notice leads, how many it
 * hides and their names, and the way to open them — so the lead can carry the fold's one control inside its own
 * line instead of a second line under it (never two notices stacked).
 */
import { createContext, useContext } from 'react';

export const NoticeFoldContext = createContext(null);

/** The fold this notice sits in, or null outside one. */
export function useNoticeFold() {
  return useContext(NoticeFoldContext);
}
