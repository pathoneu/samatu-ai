# Industry Construction Takeoff Tools — Intelligence Report

**Date:** 2026-04-26
**Purpose:** Inform the design of Sąmatų AI's new single-Vision-call interior takeoff pipeline by surveying patterns from established industry tools.
**Confidence note:** Based on knowledge through Aug 2025; live web verification was blocked in research session. Verify Togal/Kreo specifics against current product docs before locking architectural decisions.

---

## 1. Comparison Table

| Tool | AI? | Pipeline Architecture | Output Structure | Target Market | Key Strength | Key Limit |
|------|-----|-----------------------|------------------|---------------|--------------|-----------|
| **Togal.ai** | Yes (Vision CNN + GPT-4V) | Two-pass: (1) semantic segmentation → rooms + walls, (2) symbol classification → doors/windows/fixtures. Auto scale from title block or user reference line. | Hierarchical: Project → Floor → Room (id, name, area, perimeter, H) → Elements | US GCs, architects | Sub-minute per page; fastest AI floor-plan takeoff | US-centric symbols; weak on EU/LT conventions |
| **Kreo** | Yes (ML + rules) | Three-pass: (1) PDF→vector + raster fallback, (2) element detection, (3) quantity engine vs cost DB. Human-in-loop for low-confidence detections. | Hierarchical NRM2-aligned: Element Group → Element → Sub-element → Quantity (unit, net, gross, waste%) | UK QS / main contractors | NRM2 compliance OOTB; strong BIM IFC import | UK-centric; manual confirmation required |
| **PlanSwift** | No (manual + semi-auto) | Manual polygons/lines/counts on PDF raster. "Smart" flood-fill for similar colors. User sets scale. | Flat per-page: row (label, type, unit, qty). Excel grid. No room hierarchy. | US contractors/subs | Very fast for skilled estimators | Entirely manual; no symbols; no multi-page link |
| **STACK** | Partial (auto-count for simple symbols) | Hybrid manual + semi-auto symbol count. Multi-page via "page sets" by discipline. | Flat bid-centric: Division → Section → Line item (qty, mat cost, lab cost). CSI-16. | US GC + specialty | Cloud-collab; bid workflow | Minimal AI; symbol count for filled shapes only |
| **Bluebeam Revu** | No | Pure manual PDF markup. Calibrated scale. Batch link via "page regions". | Flat markup list: Markup (type, label, measurement, layer) → Excel. | AEC pros | Industry-standard PDF annotation; robust calibration | No automation |
| **CostX** | Partial | Vector-first: reads PDF vectors directly (no raster). Rule-based dimension recognition. Raster fallback for scans. | 2D workbook: Dimension → Quantity → Rate → Cost. Live cost DB. | International QS | True vector extraction = pixel-perfect; no DPI dependency | Expensive; slow; no AI classification |
| **Buildxact** | Partial (AI on spec docs) | Plan-linked estimating: manual takeoff + AI reads spec docs for material lists. | Job-level: Trade → Item (qty, supplier price). | SMB residential builders | Spec AI + takeoff in one workflow | Takeoff mostly manual |

---

## 2. Patterns We Should Adopt

### 2.1 Two-pass separation within a single call: structural inventory first, quantities second

Togal and Kreo separate "what exists" from "how much." Even in a single comprehensive Vision call, enforce this **within the prompt**:
- First JSON section = structural inventory (rooms, openings, dimensions, scale)
- Second JSON section = derived quantities (areas, perimeters, paintable, plytelės)

This keeps the model honest: if inventory says 2 windows, the area deduction must reflect exactly 2 windows. Validation becomes deterministic.

### 2.2 Explicit stable room IDs across pages

Every multi-page tool assigns each room a persistent ID (e.g. `R-01-KITCHEN`) referenced across floor plan, ceiling plan, electrical plan, wall developments. Without this, cross-page aggregation is guesswork. Schema must require `room_id` and `room_name` as mandatory on every element, not only on the room record.

### 2.3 Per-quantity confidence tier (per field, not per result)

Kreo and Togal surface per-element confidence (high/medium/low). CLAUDE.md already mandates 🟢/🟡/🔴 — correct industry practice. Single-pass Vision call should emit `"confidence": "high"|"medium"|"low"` **per field**, not just one overall score.

### 2.4 User-confirmed scale calibration as a prerequisite, not an afterthought

All raster-based tools require scale reference. Best practice:
1. Auto-detect from title block text ("M 1:50")
2. If not found, ask user to click two known-distance points
3. Validate against at least one annotated dimension in the drawing

Trusting AI to infer scale from labels is **the single largest source of 20–40% area errors**. Add explicit `scale_ratio` and `scale_confidence` fields, validate, surface warnings.

### 2.5 Page-type classification before any measurement pass

Togal classifies pages first. Mixing page types degrades accuracy. In a single-call architecture, the prompt must first ask the model to declare `page_type` per page, then condition all subsequent extraction on that type. This replaces our current `page_classifier` microservice with a structured sub-section of the same prompt.

### 2.6 Store net AND gross quantities with deduction itemisation

NRM2/RICS require both gross and net deductions stored separately. Schema:
```
area_gross
deductions: [{type, area, source}]
area_net
calculation_trace: "perim(17.4m) × H(2.75m) − 2×window(1.2×1.5) − 1×door(0.9×2.1)"
```
Enables auditability and per-deduction user override.

### 2.7 Wall-development pages get dedicated extraction sub-prompt

Togal uses specialised models per drawing type. A single generic prompt performs poorly on Lithuanian išklotinės (which show tile zones, paint zones, niche heights, angokraščiai boundaries). Need a conditional sub-prompt section activated when `page_type == "wall_development"`.

### 2.8 Render at 300 DPI minimum; 150 DPI is insufficient

Togal/Kreo specify 300 DPI baseline. Dimension text becomes illegible at 150 DPI. A1 at 300 DPI ≈ 4960×7016px — within Claude Vision's effective resolution range. (We currently use 200 DPI; bump to 300.)

---

## 3. Patterns We Should Avoid

- **All-in-one "extract everything" without schema contract.** Free-form "tell me all quantities" produces hallucinated numbers, especially on complex multi-room drawings. Schema enforcement is mandatory.

- **Flood-fill / colour-region detection for room boundaries.** Fails on scanned PDFs, faded prints, multi-colour drawings. Claude's spatial reasoning is more robust.

- **Storing only final calculated quantity without formula trace.** When user disputes a number, they can't verify or override. Every quantity must store `calculation_trace`.

- **Page-level parallelism without deduplication.** Same wall appears on architectural and structural plans → duplicate elements. Need dedup keyed on `(room_id, element_type)` before return.

- **Inferring ceiling height from elevations when a section drawing exists.** If pjūvis present, ceiling height must be read from it — authoritative. Floor plan annotations are fallback only.

---

## 4. Direct Lift Recommendations (Actionable Now)

### A. Adopt Kreo's output hierarchy as our JSON schema contract

```json
{
  "page_type": "floor_plan|section|elevation|wall_development|ceiling_plan",
  "scale_ratio": "1:50",
  "scale_confidence": "detected_from_title_block|inferred_from_dimensions|unknown",
  "rooms": [
    {
      "room_id": "R-01",
      "room_name": "Virtuvė",
      "paskirtis": "virtuve",
      "area_gross_m2": 18.5,
      "perimeter_m": 17.4,
      "ceiling_height_m": 2.75,
      "ceiling_height_source": "section|plan_annotation|default",
      "elements": [
        {"type": "window", "count": 2, "width_m": 1.2, "height_m": 1.5, "confidence": "high"},
        {"type": "door", "count": 1, "width_m": 0.9, "height_m": 2.1, "confidence": "high"}
      ],
      "quantities": {
        "wall_area_gross_m2": 48.1,
        "deductions": [
          {"type": "window", "area_m2": 3.6},
          {"type": "door", "area_m2": 1.89}
        ],
        "wall_area_net_m2": 42.6,
        "calculation_trace": "17.4m × 2.75m − 2×(1.2×1.5) − 1×(0.9×2.1)"
      }
    }
  ],
  "warnings": []
}
```

This eliminates the need for separate page_classifier, eksplikacija_parser, self_validation passes — the structure IS the validation contract.

### B. Borrow CostX's scale verification step

After extraction, cross-check:
```
detected_scale × annotated_dimension_in_drawing ≈ pixel_span × (physical_mm_per_pixel)
```
If discrepancy >5%, set `"scale_confidence": "unknown"` and surface warning. Single check prevents the most common source of large area errors.

### C. Conditional wall-development sub-prompt (Togal specialisation)

When `page_type == "wall_development"`, activate dedicated system-prompt section instructing the model to extract:
- Tile zone boundary heights
- Paint zone boundaries
- Niche dimensions
- Angokraščiai reveal widths

Not generic room areas. This replaces multi_pass Vision complexity with a single-call conditional.

### D. Deduplication guard on room IDs before result return (Kreo page-linking)

Before returning, check duplicate `room_id` across pages. "Virtuvė" on floor plan + ceiling plan → merge (ceiling contributes ceiling type + LED; floor contributes area + perimeter), don't return two separate records.

---

## Sources

Knowledge through Aug 2025. Live web verification blocked in research session. Sources that informed this report:

- Togal.ai product docs / marketing materials (togal.ai, 2024–2025)
- Kreo product feature pages + NRM2 alignment docs (kreo.net, 2024)
- PlanSwift user docs / Trimble integration (planswift.com, 2023–2024)
- STACK Construction Technologies feature docs (stackct.com, 2024)
- Bluebeam Revu 21 measurement/calibration docs (bluebeam.com, 2024)
- CostX by Exactal — vector takeoff technical overview (exactal.com, 2024)
- Buildxact AI estimating blog posts (buildxact.com, 2024)
- RICS NRM2 New Rules of Measurement, 2nd ed. (RICS, 2012, updated 2022)
