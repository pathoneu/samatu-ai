/**
 * Sprint 1: zustand store for viewer state.
 *
 * Holds viewport transform (scale + translate), current page, current tool,
 * and bidirectional-highlight target. The PDF render layer and Konva
 * annotation layer both subscribe to (different parts of) this store, so
 * they stay in sync without prop drilling.
 */
import { createStore } from 'zustand/vanilla';

export function createViewerStore() {
  return createStore((set) => ({
    scale: 1,
    translate: { x: 0, y: 0 },
    currentPage: 1,
    currentTool: 'pan',
    hoveredRoomId: null,

    setScale: (scale) => set({ scale }),
    setTranslate: (translate) => set({ translate }),
    setTransform: ({ scale, translate }) => set({ scale, translate }),
    setCurrentPage: (currentPage) => set({ currentPage }),
    setCurrentTool: (currentTool) => set({ currentTool }),
    setHoveredRoomId: (hoveredRoomId) => set({ hoveredRoomId }),
  }));
}

export const viewerStore = createViewerStore();
