// frontend/src/lib/scaleStore.js
/**
 * Sprint 3: scale-badge state.
 *
 * Holds the current drawing scale ratio (1:N) and lock flag. Lock means
 * the user has confirmed the scale; subsequent AI runs respect the
 * locked value instead of re-detecting.
 *
 * Default 50 (1:50) matches LT residential floor-plan convention.
 */
import { createStore } from 'zustand/vanilla';

export function createScaleStore() {
  return createStore((set, get) => ({
    ratio: 50,
    locked: true,
    setRatio: (value) => {
      const n = Number(value);
      if (!Number.isFinite(n) || n <= 0) return;
      set({ ratio: n });
    },
    toggleLock: () => set({ locked: !get().locked }),
  }));
}

export const scaleStore = createScaleStore();
