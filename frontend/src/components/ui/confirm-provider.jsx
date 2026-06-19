/**
 * ConfirmProvider — a promise-based replacement for native window.confirm().
 *
 * Native confirm()/alert() shatter the premium visual language with OS chrome
 * and can't be branded. This renders a shadcn AlertDialog and exposes a
 * `confirm(opts) => Promise<boolean>` via context, so a call site changes from:
 *
 *     if (window.confirm('Ištrinti?')) { ... }
 * to:
 *     const confirm = useConfirm();
 *     if (await confirm({ title: 'Ištrinti?', destructive: true })) { ... }
 *
 * (2026-06-19 — removes the biggest "hobby build" tell from the core flows.)
 */
import { createContext, useContext, useCallback, useRef, useState } from 'react';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from '@/components/ui/alert-dialog';

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
      <AlertDialog open={!!state} onOpenChange={(open) => { if (!open) settle(false); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{state?.title}</AlertDialogTitle>
            {state?.description
              ? <AlertDialogDescription>{state.description}</AlertDialogDescription>
              : null}
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => settle(false)}>
              {state?.cancelText}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => settle(true)}
              className={state?.destructive
                ? 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-600'
                : undefined}
            >
              {state?.confirmText}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error('useConfirm must be used within <ConfirmProvider>');
  return ctx;
}
