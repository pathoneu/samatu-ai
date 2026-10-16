// The printable shortcut guide as a one-page A4 PDF, made in the browser with
// no PDF library (2026-10-16). The guide is drawn on a canvas — the browser's
// own fonts keep ą č ę ė į š ų ū ž, which the PDF standard fonts cannot — and
// the canvas JPEG is wrapped in a minimal single-image PDF. The text is not
// selectable; the sheet is meant to be printed and pinned up, like Togal's.

const A4_PT = { w: 595.28, h: 841.89 };

const enc = (s) => new TextEncoder().encode(s);

/**
 * A one-page A4 PDF showing `jpeg` (Uint8Array, baseline JPEG) edge to edge.
 * pxW / pxH are the image's pixel size. Returns Uint8Array.
 */
export function jpegToA4Pdf(jpeg, pxW, pxH) {
  const parts = [];
  const offsets = [];
  let length = 0;
  const push = (chunk) => {
    const bytes = typeof chunk === 'string' ? enc(chunk) : chunk;
    parts.push(bytes);
    length += bytes.length;
  };
  const obj = (n, body) => { offsets[n] = length; push(`${n} 0 obj\n`); body(); push('\nendobj\n'); };

  const content = `q ${A4_PT.w} 0 0 ${A4_PT.h} 0 0 cm /Im0 Do Q`;
  push('%PDF-1.4\n');
  obj(1, () => push('<< /Type /Catalog /Pages 2 0 R >>'));
  obj(2, () => push('<< /Type /Pages /Kids [3 0 R] /Count 1 >>'));
  obj(3, () => push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${A4_PT.w} ${A4_PT.h}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`));
  obj(4, () => {
    push(`<< /Type /XObject /Subtype /Image /Width ${pxW} /Height ${pxH} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`);
    push(jpeg);
    push('\nendstream');
  });
  obj(5, () => push(`<< /Length ${content.length} >>\nstream\n${content}\nendstream`));
  const xref = length;
  push(`xref\n0 6\n0000000000 65535 f \n${[1, 2, 3, 4, 5].map((n) => `${String(offsets[n]).padStart(10, '0')} 00000 n \n`).join('')}`);
  push(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);

  const out = new Uint8Array(length);
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

/**
 * Draw the guide on a 2D context sized w×h px (A4 proportions). `rows` is
 * shortcutGuideRows(); colours are the Nordic Slate ink on white paper.
 * Two columns; groups never split across columns.
 */
export function drawShortcutSheet(ctx, rows, { w, h, title, subtitle, font = 'IBM Plex Sans, Arial, sans-serif', mono = 'IBM Plex Mono, Menlo, monospace' }) {
  const u = w / 1240;                       // layout unit: 1 px at 150 dpi
  const ink = '#1f2a37';
  const muted = '#5b6675';
  const accent = '#2f6b4f';
  const rule = '#d9dee4';
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, w, h);
  ctx.textBaseline = 'top';

  const margin = 80 * u;
  ctx.fillStyle = ink;
  ctx.font = `600 ${40 * u}px ${font}`;
  ctx.fillText(title, margin, margin);
  ctx.fillStyle = muted;
  ctx.font = `${20 * u}px ${font}`;
  ctx.fillText(subtitle, margin, margin + 56 * u);

  const top = margin + 110 * u;
  const colGap = 50 * u;
  const colW = (w - 2 * margin - colGap) / 2;
  const keyW = colW * 0.42;
  const lineH = 26 * u;

  // Measure a group: header + wrapped rows.
  const wrap = (text, maxW, fontSpec) => {
    ctx.font = fontSpec;
    const words = String(text).split(' ');
    const lines = [];
    let cur = '';
    for (const wd of words) {
      const next = cur ? `${cur} ${wd}` : wd;
      if (ctx.measureText(next).width > maxW && cur) { lines.push(cur); cur = wd; } else cur = next;
    }
    if (cur) lines.push(cur);
    return lines;
  };
  const labelFont = `${19 * u}px ${font}`;
  const keyFont = `500 ${18 * u}px ${mono}`;
  const layoutGroup = (g) => {
    const items = g.items.map((it) => {
      const keyLines = wrap(it.keys.join(' · '), keyW - 12 * u, keyFont);
      const labelLines = wrap(it.label, colW - keyW, labelFont);
      return { keyLines, labelLines, height: Math.max(keyLines.length, labelLines.length) * lineH + 10 * u };
    });
    return { g, items, height: 52 * u + items.reduce((s, it) => s + it.height, 0) + 24 * u };
  };
  const groups = rows.map(layoutGroup);

  // Groups in order: the left column takes them while it stays near half the total, the rest go right.
  const total = groups.reduce((s, g) => s + g.height, 0);
  let acc = 0;
  const cols = [[], []];
  for (const g of groups) {
    const left = cols[1].length === 0 && (cols[0].length === 0 || acc + g.height / 2 <= total / 2);
    cols[left ? 0 : 1].push(g);
    if (left) acc += g.height;
  }

  cols.forEach((col, ci) => {
    const x = margin + ci * (colW + colGap);
    let y = top;
    for (const { g, items } of col) {
      ctx.fillStyle = accent;
      ctx.font = `600 ${22 * u}px ${font}`;
      ctx.fillText(g.title.toUpperCase(), x, y);
      y += 34 * u;
      ctx.fillStyle = rule;
      ctx.fillRect(x, y, colW, 2 * u);
      y += 14 * u;
      for (const it of items) {
        ctx.fillStyle = ink;
        ctx.font = keyFont;
        it.keyLines.forEach((ln, i) => ctx.fillText(ln, x, y + i * lineH));
        ctx.fillStyle = ink;
        ctx.font = labelFont;
        it.labelLines.forEach((ln, i) => ctx.fillText(ln, x + keyW, y + i * lineH));
        y += it.height;
      }
      y += 24 * u;
    }
  });

  ctx.fillStyle = muted;
  ctx.font = `${16 * u}px ${font}`;
  ctx.fillText('Pathon · klavišai veikia, kai žymeklis ne teksto laukelyje', margin, h - margin + 20 * u);
}

/** Render + download in the browser. Returns the file name. */
export async function downloadShortcutSheet(rows, { mac, fileName = 'Pathon - spartieji klavisai.pdf' } = {}) {
  const w = 1240;
  const h = Math.round(w * (A4_PT.h / A4_PT.w));
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  try { await document.fonts?.ready; } catch { /* fonts API missing — fallbacks draw */ }
  drawShortcutSheet(ctx, rows, {
    w, h,
    title: 'Brėžinio peržiūra — spartieji klavišai',
    subtitle: mac ? 'macOS: ⌘ — Command, ⇧ — Shift' : 'Windows / Linux: Ctrl, Shift',
  });
  const blob = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', 0.92));
  if (!blob) throw new Error('canvas toBlob failed');
  const jpeg = new Uint8Array(await blob.arrayBuffer());
  const pdf = jpegToA4Pdf(jpeg, w, h);
  const url = URL.createObjectURL(new Blob([pdf], { type: 'application/pdf' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
  return fileName;
}
