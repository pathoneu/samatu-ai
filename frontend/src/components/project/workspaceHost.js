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
 * }
 */
import { createContext, useContext } from 'react';

export const WorkspaceHostContext = createContext(null);

export function useWorkspaceHost() {
  return useContext(WorkspaceHostContext);
}

// A panel this wide holds the question list beside the question card; narrower, they stack.
export const PANEL_TWO_COLUMNS_MIN = 680;
