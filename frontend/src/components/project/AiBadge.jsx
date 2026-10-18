import { Sparkles } from 'lucide-react';

/**
 * AiBadge — small ✨ pill marking AI-powered features.
 * Use next to button labels for actions that involve Vision / OpenCV / LLMs
 * (eksplikacija auto-reader, future click-to-fill, manual polygon AI suggest).
 *
 * Visual: cyan glow on dark chrome, dark sparkle icon.
 */
export default function AiBadge({ className = '', label = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-0.5 px-1 py-0 rounded text-[8px] font-bold uppercase tracking-wide bg-viewer-chrome-active/20 text-viewer-chrome-active border border-viewer-chrome-active/40 ${className}`}
      title="Perskaityta iš brėžinio piešinio automatiškai — verta patikrinti"
    >
      <Sparkles className="w-2.5 h-2.5" />
      <span>{label}</span>
    </span>
  );
}
