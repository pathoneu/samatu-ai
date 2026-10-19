/**
 * ConfirmProvider — a promise-based replacement for native window.confirm().
 *
 * Native confirm()/alert() shatter the premium visual language with OS chrome
 * and can't be branded. This renders the one compact confirm (ConfirmBox, 300 px with a consequence
 * sentence — Pathon v3 W5-B B6) and exposes a `confirm(opts) => Promise<boolean>` via context, so a call
 * site changes from:
 *
 *     if (window.confirm('Ištrinti?')) { ... }
 * to:
 *     const confirm = useConfirm();
 *     if (await confirm({ title: 'Ištrinti?', description: 'Kas nutiks…', destructive: true })) { ... }
 *
 * `description` is the consequence sentence: what happens, and whether it can be taken back.
 * (2026-06-19 — removes the biggest "hobby build" tell from the core flows.)
 */
import { createContext, useContext, useCallback, useRef, useState } from 'react';
import ConfirmBox from './ConfirmBox';

const ConfirmContext = createContext(null);

export function ConfirmProvider({ children }) {
  const [state, setState] = useState(null);
  const resolver = useRef(null);

  const confirm = useCallback((opts) => new Promise((resolve) => {
    resolver.current = resolve;
    setState({
      title: opts?.title || 'Patvirtinti veiksmą',
      description: opts?.description || '',
      confirmText: opts?.confirmText || 'Patvirtinti',
      cancelText: opts?.cancelText || 'Atšaukti',
      destructive: opts?.destructive ?? false,
    });
  }), []);

  const settle = useCallback((result) => {
    setState(null);
    if (resolver.current) {
      resolver.current(result);
      resolver.current = null;
    }
  }, []);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <ConfirmBox
        open={!!state}
        title={state?.title}
        consequence={state?.description}
        confirmText={state?.confirmText}
        cancelText={state?.cancelText}
        destructive={state?.destructive}
        onConfirm={() => settle(true)}
        onCancel={() => settle(false)}
      />
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error('useConfirm must be used within <ConfirmProvider>');
  return ctx;
}
