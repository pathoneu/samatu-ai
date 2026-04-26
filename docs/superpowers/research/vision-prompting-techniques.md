# Claude Vision Prompting — Best-in-Class for Architectural PDF Extraction

**Target**: `claude-opus-4-7`, multi-page LT construction PDFs, quantity takeoff JSON
**Sources**: Anthropic Vision docs, Structured Outputs docs, Prompting Best Practices, Prompt Caching docs (fetched April 2026)

> **Verification note:** Some API surface details below (e.g. `output_config.format`, `effort: "high"`) reflect the latest Anthropic SDK as researched. Before adopting in code, verify against the installed `anthropic` package version. If a feature isn't present in the SDK we have, fall back to in-prompt JSON schema + regex repair, but keep the rest of the patterns (image ordering, page labels, system prompt caching) which work regardless of SDK version.

---

## 1. Anthropic-Recommended Patterns

### 1.1 Image ordering in the content array

> "It's best to place images earlier in the prompt than questions about them or instructions for tasks that use them."
> "In situations where there are multiple images, introduce each image with `Image 1:` and `Image 2:` and so on."

**Critical bug in current V8**: `vision_extract.py` puts USER_PROMPT text FIRST, then images. Correct order:

```
[text: "Page 1 [floor_plan]:"]
[image block: page 1]
[text: "Page 2 [eksplikacija]:"]
[image block: page 2]
...N pages...
[text: final one-line extraction instruction]
```

**This is the single highest-leverage fix.** Apply before any other optimization.

### 1.2 Image size limits for Opus 4.7

> "For Claude Opus 4.7: 4784 tokens maximum, and at most 2576 pixels on the long edge."

Opus 4.7 is the first model with high-resolution support (2576 px vs 1568 px on prior models). Token cost ~3× higher at max resolution, but legibility of mm annotations on A1 drawings improves substantially.

**Token cost table** (input at $5/M tokens):

| Resolution | Tokens/image | $/image | 20 images |
|---|---|---|---|
| 1000×1000 px | ~1,334 | $0.007 | $0.13 |
| 1920×1080 px | ~2,765 | $0.014 | $0.28 |
| 2000×1500 px | ~4,000 | $0.020 | $0.40 |
| 2576 px long edge | ~4,784 | $0.024 | $0.48 |

At 200 DPI / max_dim=2000 / 20 pages: image tokens ~$0.40. + 5k system + 6k output → **total ~$0.50-0.70/call** without caching.

### 1.3 Per-request image limits

100 images per request for Opus 4.7 (200k context). >20 images → max dim reduced to 2000×2000 px. 20 pages is well within limits.

### 1.4 Files API for repeated images

For single-call extraction, base64 is fine. If self-validation second pass is added, switch to Files API `file_id` to avoid re-sending all 20 images twice.

### 1.5 Structured output — replace JSON repair with output_config.format

> "Structured outputs guarantee schema-compliant responses through constrained decoding. Always valid: No more JSON.parse() errors."

Current `_clean_json_text` + regex repair is fragile and silently corrupts data when repair guesses wrong. Replace entirely with `output_config`:
- Guaranteed valid JSON unless `stop_reason == "refusal"` or `"max_tokens"`
- Grammar compiled once, cached 24h — ~200ms extra first-call latency
- Incompatible with prefilling — but prefilling is deprecated on Opus 4.7

> "Starting with Claude 4.6 models... prefilled responses on the last assistant turn are no longer supported."

**Action:** Delete `_clean_json_text` + regex repair. Use `output_config.format`. Handle `stop_reason` explicitly.

### 1.6 Effort parameter — set explicitly to "high"

> "Use a minimum of high effort for most intelligence-sensitive use cases."

Current code has no `effort` parameter — defaults to `medium`. For architectural measurement extraction:

```python
output_config={"format": {...}, "effort": "high"}
```

Enables adaptive thinking for ambiguous scale + partially obscured annotations. Do NOT use `effort="xhigh"` (agentic/coding workloads).

### 1.7 Literal instruction following on Opus 4.7

> "Claude Opus 4.7 interprets prompts more literally... It will not silently generalize an instruction from one item to another."

Beneficial for extraction: schema `plotas_m2: number | null` → model outputs `null` when not visible rather than guessing. Design schema to treat `null` as "not found"; handle downstream in `sanity.py`.

### 1.8 Prompt caching — system prompt must exceed 4096 tokens

Cache pricing: writes $6.25/M (5-min TTL), reads $0.50/M (90% cheaper). Minimum cacheable length for Opus 4.7: **4096 tokens**.

Current SYSTEM_PROMPT (~200 tokens) and USER_PROMPT with schema (~1500 tokens) are both uncacheable. **Fix:** merge all static content (role, rules, formulas, schema, examples) into system prompt. 5k-token system block saves $0.0225/read. Break-even after 2 calls.

---

## 2. Image Preprocessing Recommendations

### 2.1 DPI and max dimension

**200 DPI, max_dim=2000 for A1 drawings. max_dim=2576 for A4 spec sheets.**

A1 (841×594 mm): 200 DPI → 6626×4677 px → resized to 2576×1818 px by Opus 4.7. 300 DPI produces same final resolution after resize — no quality gain, slower preprocessing. A4 at 200 DPI: 1654×2339 px — fits within 2576 px no resize.

Practical: keep max_dim=2000 for batch. For pages where annotations missed (confidence LOW), resubmit at max_dim=2576 in targeted single-page follow-up call.

### 2.2 Format

JPEG quality=85 for color drawings. Quality 85 = documented safe floor; below makes small text illegible. PNG only for pure B&W line drawings with sub-0.5 mm hairlines where JPEG artifacts are problematic.

### 2.3 Color vs grayscale

**Keep color.** LT drawings use color semantically: red = LED niches, blue/cyan hatching = tile zones, yellow = specific material zones. Grayscale forces reliance on text labels only.

### 2.4 Cropping

Do NOT crop for primary extraction. Send full pages — eksplikacija + scale bar + room labels must all be visible simultaneously. Per-room targeted crops are valid fallback for rooms missed during extraction (doubles cost).

---

## 3. Prompt Structure Recommendations

### 3.1 System vs user prompt split

**System prompt** (static, cache the entire block):
- Expert role (3-5 sentences)
- Extraction rules with formulas + NRM2 deduction thresholds
- Full output schema as TypeScript-style type definition
- 1-2 worked examples in `<examples>` tags
- Output format: "Respond ONLY with JSON matching schema. No prose."

**User message** (changes per call):
- Interleaved page labels + image blocks
- Per-call overrides (rangovo_profilis)
- Final one-line instruction

### 3.2 Schema definition: TypeScript-style in system prompt

```typescript
type RoomType = "gyvenamoji" | "miegamoji" | "virtuve" | "vonia" | "wc" |
                "koridorius" | "holas" | "drabuzine" | "katiline" |
                "skalbykla" | "valgomasis" | "tamburas" | "garazas";

type Room = {
  nr: string;
  pavadinimas: string;
  paskirtis: RoomType;
  puslapio_nr: number | null;
  plotas_m2: number | null;       // null = not determinable
  perimetras_m: number | null;
  lubu_aukstis_m: number;
  lubu_tipas: "gkp" | "betonas" | "pakabinamos";
  dazymo_plotas_m2: number;
  kampu_metrai: number;
  angokrasciu_gkp_m: number;
  pasleptu_duru_staktu_m: number;
  nisu_metrai: number;
  pvc_grindys_m2: number;
  plyteles_grindys_m2: number;
  plyteles_sienos_m2: number;
  isliginamasis_m2: number;
  grindjuosciu_m: number;
};

type Output = {
  archetipas: "standart" | "premium" | "renovacija" | "dideli_namu_premium";
  bendras_plotas_m2: number;
  scale_source_page: number | null;
  eksplikacija_source_page: number | null;
  patalpos: Room[];
  durys: Array<{plotis_mm: number; aukstis_mm: number; tipas: "standart" | "pasleptos"; kiekis: number}>;
  langai: Array<{plotis_mm: number; aukstis_mm: number; gkp_angokrastis: boolean; stoglangis: boolean; kiekis: number}>;
  nisos: Array<{ilgis_m: number}>;
  santrauka: {
    dazymo_plotas_total_m2: number; kampai_m_total: number;
    angokrasciu_gkp_m_total: number; pasleptu_duru_staktu_m_total: number;
    nisu_metrai_total: number; gkp_lubu_m2_total: number;
    pvc_grindys_m2_total: number; plyteles_grindys_m2_total: number;
    plyteles_sienos_m2_total: number; isliginamasis_m2_total: number;
    grindjuosciu_m_total: number; hidroizoliacijos_vnt: number;
  };
  pastabos: string;
};
```

### 3.3 XML tags for sections

Replace `# DALIS N` headers with XML:
```xml
<role>...</role>
<extraction_rules>
  <room_identification>...</room_identification>
  <quantity_formulas>...</quantity_formulas>
  <symbol_recognition>...</symbol_recognition>
  <cross_referencing>...</cross_referencing>
</extraction_rules>
<output_schema>...</output_schema>
<examples>...</examples>
```

### 3.4 Examples: 1-2 worked rooms

Include one rectangular room and one `vonia` — two most common error sources. Show one complete Room JSON object per example with drawing description above. Wrap in `<example>` tags. Don't show full 20-room output.

### 3.5 Outcome-focused instructions, not sequential CoT

Replace rigid `DALIS 1 → DALIS 2 → DALIS 3` with:

"For each room visible in any of the drawings: find its area from eksplikacija or wall measurements, apply the formulas below, output as a Room object."

Adaptive thinking (activated by `effort="high"`) handles cross-page reasoning internally. Sequential structure blocks it.

---

## 4. Multi-Page Handling

### 4.1 Page labels — second-highest-leverage change

Use `page_classifier.py` output (or per-page Vision sub-call) to generate labels:

```python
content = []
for i, page in enumerate(pages, start=1):
    page_type = page.get("page_type", "drawing")
    content.append({"type": "text", "text": f"Page {i} of {len(pages)} [{page_type}]:"})
    content.append({
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": page["image_b64"]}
    })
content.append({"type": "text", "text": "Extract all rooms and quantities from the pages above."})
```

Valid page types: `floor_plan`, `eksplikacija`, `ceiling_plan`, `wall_elevation`, `section`, `electrical_plan`, `plumbing_plan`, `specification`. Unknown → `drawing`.

### 4.2 Cross-reference instructions in system prompt

```
When eksplikacija and floor plan dimensions conflict, prefer eksplikacija area.
Dimension annotations are in mm unless labeled "m" or "m²".
Scale bar overrides any assumed scale. Record scale_source_page.
Room numbers in eksplikacija must match labels on floor plan.
When areas disagree by >10%, use larger value, note in pastabos.
```

### 4.3 Max pages and page_filter

For PDFs 30–65 pages: run page_classifier first, select 12–15 relevant pages (floor_plan, ceiling_plan, eksplikacija, wall_elevation), pass via page_filter. Current "first 20 pages" fallback must NOT be production default — classifier must drive selection.

### 4.4 Source page provenance

Top-level Output adds:
```typescript
scale_source_page: number | null;
eksplikacija_source_page: number | null;
```

When a measurement is wrong, engineer needs to know which page. Essential for production debugging.

---

## 5. Cost and Latency Table

`claude-opus-4-7`: $5/M input, $25/M output, $0.50/M cache reads.

| Scenario | Image tokens | Text tokens | Output tokens | $/call | p50 latency |
|---|---|---|---|---|---|
| 10 pages @ 1000×1000 | 13,340 | 5,000 | 4,000 | ~$0.17 | ~25s |
| 20 pages @ 2000 px (current) | ~40,000 | 5,000 | 6,000 | ~$0.38 | ~50s |
| 20 pages @ 2576 px (Opus 4.7 max) | ~80,000 | 5,000 | 6,000 | ~$0.48 | ~65s |
| 20 pages + cache hit (5k sys) | ~40,000 | 500 new | 6,000 | ~$0.23 | ~45s |
| 5 pages focused (post-classifier) | ~10,000 | 5,000 | 6,000 | ~$0.08 | ~18s |

Notes: cache saves 90% on cached tokens. `output_config` adds ~200ms first-call grammar compile, then cached 24h. `effort="high"` adds ~10–20% latency — worth it for accuracy. p95 for 20-image: 90–150s worst case — stream the response.

---

## 6. Anti-Patterns to Avoid

- **Prompt text before images.** Current V8: `content = [USER_PROMPT, ...images]`. Docs say images first.
- **JSON repair in post-processing.** `_clean_json_text` + regex silently corrupts when guess is wrong. Delete. Use `output_config.format` + explicit stop_reason check.
- **Too many optional fields.** Keep Room <20 fields. Remove `bbox_pct` entirely (current V8 already says `NEEIKVOK laiko bbox` — follow through).
- **Ambiguous enum values.** With Opus 4.7's literal following, model outputs exact enum or null. Use unambiguous names: `drabuzine` for walk-in wardrobe (not `rubine`).
- **System prompt too short to cache.** 200 tokens uncacheable. Move all rules + schema to system prompt → 5k tokens cacheable.
- **Over-urgency markers.** Multiple `SVARBU: VISADA TIKSLIAI` don't improve accuracy on Opus 4.7. One clear instruction per concept.
- **Same-call self-verification.** Model generates left-to-right, can't revise output. Same-call "verify your JSON" doesn't work. Use separate API call (2-pass) or downstream `sanity.py`.

---

## 7. Recommended Prompt Skeleton

### System prompt (cache the full block)

```python
SYSTEM_PROMPT = [
    {
        "type": "text",
        "text": """
<role>
You are a professional Lithuanian construction quantity surveyor (sąmatininkas) with 15+ years
of interior finishing experience. You apply RICS NRM2 + Lithuanian STR standards to produce
precise quantity takeoffs from architectural drawings.
Respond ONLY with a JSON object matching the schema below. No prose, no markdown fences.
</role>

<extraction_rules>

<room_identification>
For each room:
- nr: room number exactly as shown (e.g. "01", "02")
- pavadinimas: exact Lithuanian name from drawing or eksplikacija
- paskirtis: classify using RoomType enum
- plotas_m2: priority — (1) eksplikacija table, (2) inline label, (3) calculated from wall dims
- perimetras_m: sum of wall lengths in meters (from mm annotations)
- lubu_aukstis_m: default 2.82 unless section shows otherwise
- lubu_tipas: gkp if ceiling plan shows GKP framing; betonas for tamburas/garazas
</room_identification>

<quantity_formulas>
[paste formulas from CLAUDE.md sections 1.1–1.15 here, with corrections from formula-validation.md]
</quantity_formulas>

<symbol_recognition>
Doors: arc symbol (quarter-circle + rectangle outline).
Windows: two parallel lines crossing wall thickness.
LED niches: red annotation "karnizas/niša Xcm" on ceiling plan.
Tile zone: hatched area + PLYTELĖS or PT annotation.
</symbol_recognition>

<cross_referencing>
When eksplikacija and floor plan conflict on area, prefer eksplikacija.
Annotations in mm unless labeled "m" or "m²".
Scale bar overrides assumed scale. Record scale_source_page.
When areas disagree >10%, use larger value, note in pastabos.
</cross_referencing>

</extraction_rules>

<output_schema>
[full TypeScript type definition — Output and Room types]
</output_schema>

<examples>
<example>
Eksplikacija: "02 Vona 6.4 m²", ceiling H=+2850,
two walls with PLYTELĖS hatching to H=2.0m,
one hidden-frame door 700×2000mm, one window 600×1400mm.
Perimeter from wall dims: 10.2m.

{
  "nr": "02", "pavadinimas": "Vona", "paskirtis": "vonia",
  "puslapio_nr": 2, "plotas_m2": 6.4, "perimetras_m": 10.2,
  "lubu_aukstis_m": 2.85, "lubu_tipas": "gkp",
  "dazymo_plotas_m2": 8.6, "kampu_metrai": 0,
  "angokrasciu_gkp_m": 0, "pasleptu_duru_staktu_m": 4.9,
  "nisu_metrai": 0, "pvc_grindys_m2": 0,
  "plyteles_grindys_m2": 6.4, "plyteles_sienos_m2": 12.4,
  "isliginamasis_m2": 6.4, "grindjuosciu_m": 0
}
</example>
</examples>
""",
        "cache_control": {"type": "ephemeral"}   # cache 5k+ token block
    }
]
```

### User message builder

```python
def build_user_content(pages, rangovo_profilis=None):
    content = []
    # Images FIRST, interleaved with page labels
    for i, page in enumerate(pages, start=1):
        page_type = page.get("page_type", "drawing")
        content.append({"type": "text", "text": f"Page {i} of {len(pages)} [{page_type}]:"})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg",
                       "data": _resize_b64(page["image_b64"], max_dim=2000, quality=85)}
        })
    # Query LAST
    override = f"\nContractor profile: {json.dumps(rangovo_profilis)}" if rangovo_profilis else ""
    content.append({"type": "text",
                    "text": f"Extract all rooms and quantities from the {len(pages)} pages above.{override}"})
    return content
```

### API call with structured output, effort, and caching

```python
def _call_opus_v8(pages, rangovo_profilis=None):
    client = _get_client()
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=8192,
        system=SYSTEM_PROMPT,                           # list with cache_control
        messages=[{"role": "user", "content": build_user_content(pages, rangovo_profilis)}],
        output_config={
            "format": {"type": "json_schema", "schema": OUTPUT_JSON_SCHEMA},
            "effort": "high"
        }
    )
    if resp.stop_reason == "refusal":
        raise ValueError("Model refused — check drawing content")
    if resp.stop_reason == "max_tokens":
        raise ValueError("Output truncated — increase max_tokens beyond 8192")
    result = json.loads(resp.content[0].text)
    result["_usage"] = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cache_read_tokens": getattr(resp.usage, "cache_read_input_tokens", 0),
        "cache_write_tokens": getattr(resp.usage, "cache_creation_input_tokens", 0),
    }
    return result
```

---

## Summary: V8 vs Best-in-Class

| Issue | Current V8 | Best-in-class |
|---|---|---|
| Image/text ordering | Text prompt first, images after | Page label + image interleaved, query last |
| JSON reliability | Regex repair of text output | `output_config.format` JSON schema (guaranteed) |
| Effort/thinking | Not set (defaults medium) | `output_config.effort = "high"` |
| Page labeling | No labels on images | "Page N of M [floor_plan]:" before each image |
| Prompt caching | Not configured | `cache_control` on 5k+ token system block |
| Resolution | max_dim=2000 | max_dim=2576 on Opus 4.7 for fine text |
| Schema location | In user prompt as JSON template | In system prompt as TypeScript type + output_config |
| `bbox_pct` field | In schema, wastes attention | Removed from extraction call |
| Sequential CoT (DALIS 1-2-3) | Manual, blocks cross-page reasoning | Outcome-focused + adaptive thinking |
| JSON parse errors | Silent regex repair | Explicit stop_reason check + ValueError |

---

## Top 7 Findings (Action Priorities)

1. **Image ordering wrong in V8** — text before images violates docs. Fix first. Likely accounts for some accuracy issues.
2. **Use `output_config.format` with JSON schema** — eliminates regex repair, guaranteed valid JSON. Compatible with Opus 4.7.
3. **Add `effort: "high"`** — V8 defaults to medium. Likely cause of shallow reasoning on complex multi-room drawings.
4. **Page labels in content array** — V8 has page_classifier but doesn't use it for labeling Vision input.
5. **System prompt 4096+ tokens for caching** — move all extraction rules + schema to system prompt + cache_control.
6. **Opus 4.7 supports 2576 px long edge** — upgrade for A4 spec sheets with dense text.
7. **Remove `bbox_pct` from schema** — V8 already notes it wastes attention; follow through and delete.

---

*Sources:*
- [Anthropic Vision docs](https://platform.claude.com/docs/en/build-with-claude/vision.md)
- [Structured Outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs.md)
- [Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices.md)
- [Prompt Caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching.md)
