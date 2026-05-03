# Sprint 0 Pre/Post Snapshot Plan

**Status:** TODO — to be run manually by Ignas before Sprint 1 starts.

## Test PDFs

Pick 3 representative interior PDFs (one simple, one with soffits/wet rooms, one mixed):

- P1: TBD path
- P2: TBD path
- P3: TBD path

## Procedure

For each PDF, run with all Sprint-0 flags ON:

```bash
export ENABLE_PER_ROOM_CEILING=1
export ENABLE_PAINT_CLASS_INFERENCE=1

cd backend && python -c "
from extractor.vision_call import extract_interior
import json
result = extract_interior('TBD/P1.pdf')
with open('docs/snapshots/2026-05-03-P1-post.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
"
```

Repeat for P2, P3.

## Verification points (per Sprint 0 fix)

- Fix 1 (GKP split): pozicijos contains both "GKP lapai sienoms (12.5 mm)" and "GKP lapai luboms (9.5 mm)" lines (when both wall + ceiling GKP present)
- Fix 4 (per-room ceiling): if PDF has soffits, `lubu_auksciai` dict populated; rooms have varied `lubu_aukstis_m`
- Fix 5 (paint class inference): if PDF spec is explicit (Q2/Q3/Q4), `paint_class_source == "inferred_from_spec"`
- Fix 3 (scale verification): `warnings` array contains scale messages if applicable

## Why this is deferred

Running real PDFs through Vision costs ~$0.50/PDF and requires representative test files. The Sprint-0 plan acceptance criteria includes this as a checkpoint; subagent context lacks both the API budget and the curated test PDFs. Ignas to run before Sprint 1 kickoff.
