/**
 * ConfirmBox — the one compact confirm (Pathon v3 W5-B, B6; coverage #162; design §6 „300 px confirm boxes",
 * Togal's compact confirm). 300 px, a title, ONE consequence sentence („Projektas taps toks, koks buvo …"),
 * then Atšaukti / the act. It replaces the big centred AlertDialog every `useConfirm()` call opened
 * (components/ui/confirm-provider.jsx renders this), so the viewer's ad-hoc dialogs — removing an edition,
 * deleting a takeoff mark, restoring a version — all look and behave the same.
 *
 * Kept for acts that have no Undo of their own. Rimas' rule stands (docs/superpowers/plans/
 * 2026-09-04-rimo-kelione.md §1.5): where a write can be undone, the toast's „Atšaukti" is the safety, not a
 * question.
 *
 * Keys: Esc = Atšaukti and Enter presses the focused button — both taken here in the capture phase and stopped,
 * so the viewer's own Esc order (lib/escOrder) and its Enter listeners never see a press meant for the box.
 * Focus starts on Atšaukti (the safe answer).
 */
import { useEffect, useRef } from 'react';
import * as AlertDialogPrimitive from '@radix-ui/react-alert-dialog';
import { cn } from '@/lib/utils';

export default function ConfirmBox({
  open, title, consequence = '', confirmText = 'Patvirtinti', cancelText = 'Atšaukti', destructive = false,
  onConfirm, onCancel,
}) {
  const boxRef = useRef(null);
  const cancelRef = useRef(onCancel);
  cancelRef.current = onCancel;
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopImmediatePropagation();
        cancelRef.current?.();
      } else if (e.key === 'Enter' && boxRef.current?.contains(e.target)) {
        e.stopImmediatePropagation();       // the focused button still gets its click (the default action)
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [open]);
  return (
    <AlertDialogPrimitive.Root open={!!open} onOpenChange={(o) => { if (!o) onCancel?.(); }}>
      <AlertDialogPrimitive.Portal>
        <AlertDialogPrimitive.Overlay className="fixed inset-0 z-50 bg-foreground/20" />
        <AlertDialogPrimitive.Content
          ref={boxRef}
          onEscapeKeyDown={(e) => e.preventDefault()}
          className="fixed left-1/2 top-1/2 z-50 w-[300px] max-w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 rounded-panel border border-border bg-card text-card-foreground shadow-lg p-4"
          data-testid="confirm-box"
        >
          <AlertDialogPrimitive.Title className="text-ui font-semibold text-foreground">{title}</AlertDialogPrimitive.Title>
          {consequence ? (
            <AlertDialogPrimitive.Description className="mt-1.5 text-ui text-muted-foreground leading-snug" data-testid="confirm-consequence">
              {consequence}
            </AlertDialogPrimitive.Description>
          ) : (
            <AlertDialogPrimitive.Description className="sr-only">{title}</AlertDialogPrimitive.Description>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <AlertDialogPrimitive.Cancel
              className="h-9 px-3 rounded-panel border border-border bg-card text-ui text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => onCancel?.()}
              data-testid="confirm-cancel"
            >{cancelText}</AlertDialogPrimitive.Cancel>
            <AlertDialogPrimitive.Action
              className={cn(
                'h-9 px-3 rounded-panel text-ui font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                // the act itself in the dark ink — red is kept for errors (overlay vocabulary); the words say what happens
                destructive ? 'bg-foreground text-background hover:bg-foreground/90' : 'bg-primary text-primary-foreground hover:bg-primary/90',
              )}
              onClick={() => onConfirm?.()}
              data-testid="confirm-ok"
            >{confirmText}</AlertDialogPrimitive.Action>
          </div>
        </AlertDialogPrimitive.Content>
      </AlertDialogPrimitive.Portal>
    </AlertDialogPrimitive.Root>
  );
}
