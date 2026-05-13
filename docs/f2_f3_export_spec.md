# F2/F3 Export Specification (Week 7 — D7 LT moat)

## F2 — Atliktų darbų aktas

Per-line columns (CSV order):

| # | Column | Source |
|---|---|---|
| 1 | Eil. Nr. | builder index |
| 2 | Kodas | `lines[].code` |
| 3 | Pavadinimas | `lines[].label_lt` |
| 4 | Mato vnt. | `lines[].unit` |
| 5 | Kiekis | `lines[].quantity` |
| 6 | Vieneto kaina (be PVM) | `lines[].unit_price_eur_be_pvm` |
| 7 | Suma (be PVM) | qty × price |
| 8 | Confidence | `lines[].confidence` (🟢🟡🔴) |
| 9 | Šaltinis | AI / Rule / User / Verified |
| 10 | Šaltiniai puslapiai | `lines[].source_pages[]` |
| 11 | Audito istorija | semicolon-joined `audit_history[]` |
| 12 | Pastabos | `lines[].notes` |

Footer:

- `Iš viso be PVM` — sum of column 7.
- `Iš viso su PVM` — only when `vat_mode=with_pvm`.
- `Atvirkštinis PVM …` — only when `vat_mode=reverse_vat` (renovation >10y).

## F3 — Pažyma apie atliktų darbų vertę

F3 reuses the same row schema and JSON payload (`format=f3` marker).
Aggregation by section happens at the downstream rendering layer; the
backend ships the same audit-aware data so an estimator can attach either
form to a single project review.

## VAT modes

| `vat_mode` | When to use | Effect |
|---|---|---|
| `be_pvm` (default) | Inter-business invoicing | Exports without PVM |
| `with_pvm` | Direct customer billing | Adds 21% column at totals |
| `reverse_vat` | Renovation >10y | Totals stay be-PVM, footer notes atvirkštinis PVM |

`project_age_years` is taken as a hint for `reverse_vat` correctness but
isn't enforced (the user signs off via the export button choice).

## Provenance preservation — the LT moat

Every row carries:

- `source` — `ai`, `rule`, `user`, or `verified` (Patikrinta).
- `audit_history` — list of human-readable correction reasons like
  `"5.0→6.5 (extra reveal at hidden door)"` or `"Patikrinta"`.

This is the LT-specific defensibility against frontier-model document
agents (Council R5): when a contractor disputes a quantity, the export
shows AI-vs-human values and the reason for the change. No competitor in
this price band exposes this audit chain at the row level.

## API endpoints

- `GET /api/export/v2/f2/{project_id}.json?vat_mode=...&project_age_years=...`
- `GET /api/export/v2/f2/{project_id}.csv?vat_mode=...`
- `GET /api/export/v2/f3/{project_id}.json?vat_mode=...`

The endpoints currently return `501 Not Implemented` until the project
lines store is wired (lives at `data/projects/<id>/lines.json`). The
export builder is fully tested via direct function calls in
`backend/tests/extractor/test_f2_export.py` (8 cases).

## Storage

Lines come from `data/projects/<project_id>/lines.json` (a flat JSON list
of line dicts). Audit events come from `data/corrections/<project_id>.jsonl`
(written by Week 5 corrections API). The export builder joins them by
`code` and produces both JSON and CSV outputs.

When auth + DB land, swap the file-system stores for DB tables; the
builder signature stays the same.
