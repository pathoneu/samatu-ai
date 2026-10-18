/**
 * workspaceHost — what the project workspace offers the contents of its right panel (Pathon v3, track A).
 *
 * Present (non-null) only when a component is rendered INSIDE the workspace's panel — Patikra's question
 * list and room sheet use it to lay themselves out for the panel instead of a whole page, and to hand
 * their copy of the project back to the frame. Absent, they behave exactly as the standalone pages did.
 *
 * Value: {
 *   panelWidth,                     // px of the right panel (layout decisions: one column or two)
 *   onProjectChange(project),       // their saved project, mirrored to the frame (no second save)
 *   // two-way highlight hooks (A6)
 *   onRevealEvidence({ page, rect_pct }), // the workspace drawing jumps to that place and frames it
 *   onFocusRoom(nr),                // the workspace drawing focuses that room (its page, its ring)
 *   // the workspace drawing lent to a check view (RoomDrawingPane)
 *   canvasReady,                    // the drawing is the EmbedPDF viewer with a PDF, on screen
 *   canvasSlot,                     // DOM node above the drawing for the check view's own controls
 *   setCanvasCheck({ check, pickActive } | null), // what the drawing shows instead of the room zones
 *   pointRef,                       // ref: (point) => void — where a click on the drawing goes while picking
 * }
 */
import { createContext, useContext } from 'react';

export const WorkspaceHostContext = createContext(null);

export function useWorkspaceHost() {
  return useContext(WorkspaceHostContext);
}

// A panel this wide holds the question list beside the question card; narrower, they stack.
export const PANEL_TWO_COLUMNS_MIN = 680;
