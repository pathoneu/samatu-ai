/**
 * debouncedRun — the wait-then-run behind the Nustatymai recompute, and the order its answers land in.
 *
 * `createDebouncedRun(ms)`: `schedule(run)` replaces whatever was waiting and starts the wait again, so a
 * burst of edits makes ONE backend call; `flush()` runs what is waiting right now. The drawer closing
 * flushes it (2026-10-06): dropping it, as the panel used to on unmount, kept the new setting beside the
 * old rows — a silently stale sąmata.
 *
 * `createRequestOrder()`: the newest request per key (the project) wins. It is shared by every mount of
 * the panel, because a run flushed on close can still be answering when the drawer is open again — an
 * edit made then must supersede that answer.
 *
 * No React, no DOM: the timers can be handed in, so the rule is tested without a browser.
 */

export function createDebouncedRun(delayMs, { setTimer = setTimeout, clearTimer = clearTimeout } = {}) {
  let timer = null;
  let waiting = null;
  const fire = () => {
    const run = waiting;
    timer = null;
    waiting = null;
    run?.();
  };
  return {
    /** Wait `delayMs`, then call `run` — unless another run is scheduled first, which replaces it. */
    schedule(run) {
      if (timer !== null) clearTimer(timer);
      waiting = run;
      timer = setTimer(fire, delayMs);
    },
    /** Call the waiting run now; false when nothing was waiting. */
    flush() {
      if (timer === null) return false;
      clearTimer(timer);
      fire();
      return true;
    },
  };
}

export function createRequestOrder() {
  const latest = new Map();
  return {
    /** A new request for `key`: from now on only its answer counts. */
    next(key) {
      const id = (latest.get(key) || 0) + 1;
      latest.set(key, id);
      return id;
    },
    /** Is request `id` still the newest for `key`? */
    isLatest(key, id) {
      return latest.get(key) === id;
    },
  };
}
