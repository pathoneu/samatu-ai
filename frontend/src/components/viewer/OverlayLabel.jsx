/**
 * OverlayLabel — the one label pill drawn ON the sheet (Pathon v3 W1-C overlay vocabulary): white pill,
 * slate ink, the app's sans at 12 px with tabular numbers, a thin border whose colour repeats the kind
 * of the thing it names (never the only carrier of meaning — the words are). One or two lines.
 *
 * SVG, pointer-transparent: it never takes a click from the tools underneath.
 */
import { LABEL_FONT_PX, LABEL_STYLE, labelWidth, ov, paint } from '@/lib/overlayTokens';

const LINE_H = 16;
const PAD_Y = 3;

export default function OverlayLabel({
  x, y, text, sub = null, border = null, anchor = 'middle', strong = true, ink = null, ...rest
}) {
  if (!text) return null;
  const lines = sub ? [text, sub] : [text];
  const w = Math.max(...lines.map((l) => labelWidth(l)));
  const h = lines.length * LINE_H + PAD_Y * 2;
  const x0 = anchor === 'start' ? x - 6 : x - w / 2;
  const tx = anchor === 'start' ? x0 + 7 : x;
  const top = y - h / 2;
  return (
    <g pointerEvents="none" {...rest}>
      <rect
        x={x0} y={top} width={w} height={h} rx={2}
        style={paint({ fill: ov('label-bg'), stroke: border || ov('selected', 0.35) })}
        fillOpacity={0.96} strokeWidth={1}
      />
      {lines.map((line, i) => (
        <text
          key={i}
          x={tx}
          y={top + PAD_Y + LINE_H * i + 12}
          textAnchor={anchor === 'start' ? 'start' : 'middle'}
          fontSize={LABEL_FONT_PX}
          fontWeight={i === 0 && strong ? 600 : 400}
          style={{ ...LABEL_STYLE, ...paint({ fill: ink || ov('label-fg') }) }}
        >
          {line}
        </text>
      ))}
    </g>
  );
}
