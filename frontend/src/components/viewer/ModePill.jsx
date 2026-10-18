/**
 * ModePill — the bottom-centre pill on the drawing (Pathon v3 click model, W1-B B2): the active mode's
 * name, what it holds now, its keys, and the buttons that finish or leave it. Content from
 * lib/modePill (pure, tested); `onAction(id)` is the viewer's. Nothing at rest.
 */
export default function ModePill({ pill, sentence = null, onAction }) {
  if (!pill) return null;
  return (
    <div
      role="status"
      aria-label={`Įrankis: ${pill.name}`}
      data-testid="mode-pill"
      data-mode={pill.id}
      className="pointer-events-auto max-w-full rounded-panel border border-border bg-card text-ui text-foreground shadow-md px-3 py-1.5 flex flex-wrap items-center justify-center gap-x-3 gap-y-1"
    >
      <span className="font-semibold whitespace-nowrap">{pill.name}</span>
      {pill.detail && <span className="text-foreground">{pill.detail}</span>}
      {sentence && <span className="text-foreground">{sentence}</span>}
      {pill.keys && <span className="text-muted-foreground">{pill.keys}</span>}
      {pill.actions.length > 0 && (
        <span className="inline-flex items-center gap-1.5">
          {pill.actions.map((a) => (
            <button
              key={a.id}
              type="button"
              disabled={a.disabled}
              title={a.title || undefined}
              onClick={() => onAction?.(a.id)}
              data-testid={a.id === 'outlineSave' ? 'outline-edit-save' : a.id === 'outlineUndo' ? 'outline-edit-undo' : `pill-${a.id}`}
              className={`h-8 px-3 rounded whitespace-nowrap font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 disabled:cursor-not-allowed ${a.primary
                ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                : 'border border-border bg-card text-foreground hover:bg-muted'}`}
            >
              {a.label}
            </button>
          ))}
        </span>
      )}
    </div>
  );
}
