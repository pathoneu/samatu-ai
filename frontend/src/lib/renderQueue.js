/**
 * Sprint 1: bounded concurrency for pdf.js page renders.
 *
 * pdf.js spawns one worker thread already, but each page.render() call
 * eats main-thread cycles for canvas blitting. Without a cap, scrolling
 * 65 thumbnails kicks off 65 parallel renders and the UI thrashes.
 *
 * Default N=2 matches navigator.hardwareConcurrency / 2 on typical
 * 4-core devices.
 */
import pLimit from 'p-limit';

export function createRenderQueue(concurrency = 2) {
  const limit = pLimit(concurrency);
  return (job) => limit(job);
}

export const renderQueue = createRenderQueue(2);
