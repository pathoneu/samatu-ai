"""
Vision classifier per SoM image.

Skirtumai nuo V7:
- Vision NEMATAVO plotų (jau apskaičiuoti vector'iškai)
- Vision tik KLASIFIKUOJA: per pažymėtą polygon — pavadinimas + paskirtis
- Trumpas JSON output → mažiau truncation rizikos
- Multi-pass susukai išorėj (ne čia)
"""
from __future__ import annotations
import json
import os
import re
import time
from typing import Any

import anthropic


VISION_MODEL = "claude-opus-4-7"
MAX_OUTPUT_TOKENS = 4096


CLASSIFY_PROMPT = """Brėžinyje pažymėjau {n} regionų raudonais skaičiais.

Per kiekvieną regioną grąžink JSON:
- "polygon_id": integer (kaip skaičius brėžinyje)
- "pavadinimas": kambario pavadinimas (pvz "Svetainė", "Vonia 1", "Garažas")
- "paskirtis": viena iš:
  gyvenamoji, miegamoji, vonia, wc, virtuve, valgomasis, koridorius,
  holas, drabuzine, sandeliukas, tambūras, garazas, katiline, skalbykla
- "lubu_aukstis_m": jei matosi pjūvyje arba užrašyta (+2820 → 2.82). Jei ne, palik 2.82
- "is_open_space": true jei matomi keli kambariai sujungti (svetainė+valgomasis+virtuvė)

SVARBU:
- Pavadinimą imti TIKSLŲ iš brėžinio (jei užrašyta "Svetainė-valgomasis-virtuvė" — taip ir grąžink)
- Paskirtis turi būti iš sąrašo aukščiau (NE kitokia)
- NEMATUOK plotų ir perimetrų — jie jau apskaičiuoti programos
- Jei nesi tikras dėl regiono — paskirtis "gyvenamoji" default

Output (TIK JSON):
```json
{{
  "rooms": [
    {{"polygon_id": 0, "pavadinimas": "...", "paskirtis": "...",
      "lubu_aukstis_m": 2.82, "is_open_space": false}}
  ]
}}
```
"""


def classify_rooms_with_som(
    image_b64: str,
    polygons_count: int,
    n_passes: int = 1,
) -> dict:
    """Vision call: klasifikacija per pažymėtus regionus.

    Args:
        image_b64: SoM perdengtas paveikslas (base64 JPEG)
        polygons_count: kiek polygons pažymėta
        n_passes: 1 (default) arba 3 (multi-pass median voting)

    Returns:
        {"rooms": [{polygon_id, pavadinimas, paskirtis, ...}], "_passes": n}
    """
    if not image_b64:
        return {"rooms": [], "error": "no image"}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"rooms": [], "error": "no API key"}

    client = anthropic.Anthropic(api_key=api_key, timeout=60.0)

    def single_pass() -> list[dict]:
        prompt = CLASSIFY_PROMPT.format(n=polygons_count)
        try:
            resp = client.messages.create(
                model=VISION_MODEL,
                max_tokens=MAX_OUTPUT_TOKENS,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": "image/jpeg",
                            "data": image_b64,
                        }},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            # Repair + parse
            cleaned = re.sub(r'^```(?:json)?\s*\n', '', text)
            cleaned = re.sub(r'\n```\s*$', '', cleaned)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                # Auto-repair
                fixed = re.sub(
                    r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:',
                    r'\1"\2":', cleaned,
                )
                fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
                parsed = json.loads(fixed)
            return parsed.get("rooms", [])
        except Exception as e:
            print(f"[V9 classify] pass failed: {e}")
            return []

    # Multi-pass voting
    if n_passes <= 1:
        rooms = single_pass()
        return {"rooms": rooms, "_passes": 1}

    all_rooms = []
    for i in range(n_passes):
        all_rooms.append(single_pass())

    # Per polygon_id — majority vote per pavadinimas+paskirtis
    from collections import Counter, defaultdict
    by_id = defaultdict(list)
    for pass_rooms in all_rooms:
        for r in pass_rooms:
            pid = r.get("polygon_id")
            if pid is not None:
                by_id[pid].append(r)

    merged = []
    for pid, versions in by_id.items():
        if len(versions) < n_passes / 2:
            continue  # neaišku — drop
        names = [v.get("pavadinimas", "") for v in versions if v.get("pavadinimas")]
        paskirtys = [v.get("paskirtis", "") for v in versions if v.get("paskirtis")]
        is_open = sum(1 for v in versions if v.get("is_open_space")) > len(versions) / 2
        h_vals = [v.get("lubu_aukstis_m", 2.82) for v in versions]
        merged.append({
            "polygon_id": pid,
            "pavadinimas": Counter(names).most_common(1)[0][0] if names else "Patalpa",
            "paskirtis": Counter(paskirtys).most_common(1)[0][0] if paskirtys else "gyvenamoji",
            "lubu_aukstis_m": sorted(h_vals)[len(h_vals) // 2] if h_vals else 2.82,
            "is_open_space": is_open,
            "_vote_consensus": len(versions) / n_passes,
        })

    return {"rooms": merged, "_passes": n_passes}
