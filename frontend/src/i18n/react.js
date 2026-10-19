/**
 * The app's useTranslation / Trans — react-i18next's, bound to OUR i18next instance explicitly.
 *
 * Why (2026-10-19, Safari walk): react-i18next keeps the instance that `initReactI18next` registered in a
 * module-level variable. When the browser ends up with two copies of the react-i18next module — a Vite
 * dev server whose optimised-deps cache was rewritten under it (the shared node_modules/.vite trap), a
 * stale cached chunk — every component that reached the second copy found no instance, and react-i18next
 * then returns the KEY as the text. The founder saw „project.sanity.pillWarnings" all over the workspace.
 * Passing the instance as the `i18n` option makes each call independent of that module variable, so a
 * second copy still translates. Import from here, never from 'react-i18next' (eslint enforces it).
 */
import { createElement } from 'react';
import { useTranslation as useTranslationBase, Trans as TransBase } from 'react-i18next';
import i18n from './index.js';

// One stable object: react-i18next memoises on the options object, so a fresh `{ i18n }` per render would
// make it resubscribe on every render. Every call site in the app passes no options.
const BOUND = { i18n };

export function useTranslation(ns, options) {
  return useTranslationBase(ns, options ? (options.i18n ? options : { ...options, i18n }) : BOUND);
}

export function Trans(props) {
  return createElement(TransBase, props.i18n ? props : { ...props, i18n });
}
