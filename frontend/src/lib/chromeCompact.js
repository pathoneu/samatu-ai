/**
 * chromeCompact — when the viewer's top-right row (sheet pill · „Perskaityti iš naujo" · „Palyginti leidimus" ·
 * search) shows its buttons as icons only (B2-B item 4). With the drawing beside the sąmata rows at 1280 the
 * row was narrower than the pill plus the labelled buttons, it wrapped, and the second line covered the sheet's
 * title. The row no longer wraps (the pill's sheet name truncates instead); this decides when the labels go so
 * the name keeps its room. Pure: the hook (components/viewer/useChromeCompact) measures.
 *
 * `pillNatural` = the pill's width with its name untruncated (up to the name's own cap). Compact as soon as the
 * labelled card no longer fits beside it; back to labels only when the row is wide enough for the card at its
 * labelled width again (remembered when it went compact) — no flicker between the two.
 */
export const CHROME_GAP_PX = 8;

/**
 * @param {{compact: boolean, fullWidth: number|null}} state
 * @param {{rowWidth: number, pillNatural: number, cardWidth: number}} m
 * @returns {{compact: boolean, fullWidth: number|null}}
 */
export function nextChromeCompact(state, { rowWidth, pillNatural, cardWidth }) {
  if (!(rowWidth > 0)) return state;
  if (!state.compact) {
    if (pillNatural + CHROME_GAP_PX + cardWidth > rowWidth + 0.5) return { compact: true, fullWidth: cardWidth };
    return state;
  }
  const full = state.fullWidth || 0;
  if (full && pillNatural + CHROME_GAP_PX + full <= rowWidth) return { compact: false, fullWidth: null };
  return state;
}

/** The pill's untruncated width: its width plus what its truncated name hides (the name's cap `nameCap`). */
export function pillNaturalWidth(pillWidth, nameScrollWidth, nameClientWidth, nameCap = 220) {
  const hidden = Math.max(0, Math.min(nameScrollWidth || 0, nameCap) - (nameClientWidth || 0));
  return pillWidth + hidden;
}
