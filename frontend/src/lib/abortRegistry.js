// frontend/src/lib/abortRegistry.js
/**
 * Sprint 2: rapid sequential gestures abort prior in-flight requests.
 * One AbortController per gesture-kind (g1, g2, ...). takeSignal() aborts
 * the prior controller for that kind and returns a fresh AbortSignal.
 *
 * Spec §4.7: cancellation via AbortController.
 */
export function createAbortRegistry() {
  const controllers = new Map();
  return {
    takeSignal(kind) {
      const prior = controllers.get(kind);
      if (prior) prior.abort();
      const ac = new AbortController();
      controllers.set(kind, ac);
      return ac.signal;
    },
    cancelAll() {
      for (const ac of controllers.values()) ac.abort();
      controllers.clear();
    },
  };
}

export const abortRegistry = createAbortRegistry();
