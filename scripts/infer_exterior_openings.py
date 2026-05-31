"""Infer ``_exterior`` flags on gt_dimensions openings via principled rules.

Vision's per-opening _exterior flag is unreliable on Beržų — some panoramic
windows on the facade weren't flagged. Rather than re-running Vision (cost),
we infer from drawing context: opening dimensions + room type are strong
signals for exterior-vs-interior on Lithuanian residential plans.

Rules (conservative — bias toward exterior=True only when confident):

    1. Garažas — any door is exterior (garage door faces outside).
    2. Door width ≥ 1500 mm — terrace / patio / large entry door, always
       opens to the facade.
    3. Window width ≥ 2000 mm — panoramic window, always exterior on LT
       residential builds.
    4. Tambūras — the labeled "entrance" room. Its 900mm exterior door is
       already correctly flagged by Vision (don't touch).
    5. paskirtis ∈ {vonia, wc, san, koridorius, holas, drabuzine, rubine,
       skalbykla, katiline} — windows in these rooms are *more often than
       not* exterior (they're on the facade), but conservatively leave
       Vision's reading.

We never override _exterior=True back to False (Vision was confident).
We never invent openings.

Output: rewrites ground_truth/<project>/truth.json in place; the eval
re-derives n_exterior_doors / n_exterior_windows from `_elementai_to_counts`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def infer_room_exteriors(room: dict) -> tuple[int, list[str]]:
    """Mutate room['elementai'] in place; return (count_changed, change_log)."""
    paskirtis = (room.get("paskirtis") or "").lower()
    name = (room.get("pavadinimas") or "").lower()
    is_garage = paskirtis in ("garazas", "garažas") or "garaž" in name

    changes: list[str] = []
    count = 0
    for el in room.get("elementai") or []:
        tipas = (el.get("tipas") or "").lower()
        if el.get("_exterior"):
            continue
        plotis_mm = el.get("plotis_mm") or 0
        rule = None

        if tipas in ("duris", "pasleptos_duris"):
            if is_garage:
                rule = "garage door"
            elif plotis_mm >= 1500:
                rule = f"terrace/wide door ({plotis_mm}mm)"
        elif tipas in ("langas", "stoglangis"):
            if plotis_mm >= 2000:
                rule = f"panoramic window ({plotis_mm}mm)"

        if rule:
            el["_exterior"] = True
            count += 1
            changes.append(
                f"  {room.get('nr')} {room.get('pavadinimas')}: "
                f"{tipas} {plotis_mm}mm → exterior ({rule})"
            )
    return count, changes


def main(argv: list[str]) -> int:
    project_id = argv[1] if len(argv) > 1 else "berzas"
    path = REPO_ROOT / "ground_truth" / project_id / "truth.json"
    if not path.exists():
        print(f"ERR: {path} not found")
        return 2

    truth = json.loads(path.read_text())
    total = 0
    log: list[str] = []
    for room in truth.get("gt_dimensions") or []:
        n, changes = infer_room_exteriors(room)
        total += n
        log.extend(changes)

    if total == 0:
        print(f"No changes inferred for {project_id}.")
        return 0

    path.write_text(json.dumps(truth, ensure_ascii=False, indent=2))
    print(f"{project_id}: flagged {total} additional exterior openings:")
    for line in log:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
