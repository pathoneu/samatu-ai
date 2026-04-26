"""
Phase 2 — Specialized extractors.
Parallel Vision calls with Phase 1 context injected into each prompt.
"""
import asyncio
import pathlib
import time
from anthropic import Anthropic
from vision_tools import TOOL_FOR_PAGE_TYPE

VISION_MODEL = "claude-opus-4-7"
_client: Anthropic | None = None
_PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"

# Filename mapping for page types that have non-trivial names
_PROMPT_FILE: dict[str, str] = {
    "pertvarų": "phase2_pertvarų.txt",
    "išklotinė": "phase2_išklotinė.txt",
    "lubų": "phase2_lubų.txt",
    "grindų": "phase2_grindų.txt",
    "santechnikos": "phase2_santechnikos.txt",
    "rozecių": "phase2_rozecių.txt",
    "apšvietimo": "phase2_apšvietimo.txt",
}


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _load_prompt(page_type: str) -> str:
    fname = _PROMPT_FILE.get(page_type)
    if not fname:
        raise ValueError(f"No prompt file for page type: {page_type!r}")
    path = _PROMPTS_DIR / fname
    return path.read_text(encoding="utf-8")


def build_phase1_context_string(phase1: dict) -> str:
    rooms = phase1.get("patalpos", [])
    rooms_summary = ", ".join(
        f"{r['nr']}: {r['pavadinimas']} ({r['plotas_m2']}m²)"
        for r in rooms[:15]
    )
    features = phase1.get("features", {})
    features_str = ", ".join(k for k, v in features.items() if v is True)

    return (
        f"PROJECT CONTEXT:\n"
        f"- Complexity: {phase1.get('sudetingumo_klase', 'unknown')}\n"
        f"- Total area: {phase1.get('bendras_plotas_m2', '?')} m² (excl. garage)\n"
        f"- Rooms ({len(rooms)}): {rooms_summary}\n"
        f"- Special features: {features_str or 'none'}\n"
        f"- Ceiling height: {phase1.get('lubu_aukstis_m', 2.8)}m\n"
    )


def _build_prompt(page_type: str, phase1: dict) -> str:
    template = _load_prompt(page_type)
    context = build_phase1_context_string(phase1)
    try:
        return template.format(
            context=context,
            page_type=page_type,
            rooms_count=len(phase1.get("patalpos", [])),
            complexity=phase1.get("sudetingumo_klase", "unknown"),
        )
    except KeyError:
        # If template has unexpected placeholders, inject context at top
        return f"{context}\n\n{template}"


def _call_vision_with_tool(b64: str, prompt: str, page_type: str, pno: int) -> dict | None:
    """Synchronous single-page extractor call."""
    tool = TOOL_FOR_PAGE_TYPE[page_type]
    client = _get_client()

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=VISION_MODEL,
                max_tokens=4096,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            for block in response.content:
                if block.type == "tool_use":
                    return {"page_type": page_type, "pno": pno, "data": dict(block.input)}
            return None
        except Exception as exc:
            if attempt == 2:
                print(f"[phase2] page {pno} {page_type} failed after 3 tries: {exc}")
                return None
            time.sleep(2 ** attempt)
    return None


async def phase2_extract_all(
    pages_with_types: list[tuple[int, str, str]],
    phase1: dict,
) -> dict[str, list[dict]]:
    """
    Parallel Phase 2 extraction.

    Args:
        pages_with_types: list of (page_number, page_type, base64_jpeg)
        phase1: output from phase1_analyze_project

    Returns:
        dict keyed by page_type, each value is list of extracted dicts per page
    """
    loop = asyncio.get_event_loop()

    tasks = []
    for pno, page_type, b64 in pages_with_types:
        if page_type not in TOOL_FOR_PAGE_TYPE:
            continue
        prompt = _build_prompt(page_type, phase1)
        tasks.append(
            loop.run_in_executor(None, _call_vision_with_tool, b64, prompt, page_type, pno)
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    grouped: dict[str, list[dict]] = {}
    for r in results:
        if isinstance(r, Exception) or r is None:
            continue
        page_type = r["page_type"]
        grouped.setdefault(page_type, []).append(r["data"])

    return grouped


def merge_phase2_results(grouped: dict[str, list[dict]], phase1: dict) -> dict:
    """
    Merge Phase 2 results per page type into a single quantity dict.
    Multiple pages of the same type are combined (summed or merged by logic).
    """
    merged: dict = {}

    # --- Pertvarų (partition plan) — use first result, it covers the whole floor ---
    pertvaru_list = grouped.get("pertvarų", [])
    if pertvaru_list:
        p = pertvaru_list[0]
        merged["visu_kampu_vnt"] = p.get("visu_kampu_vnt", 0) or 0
        merged["isoriniu_kampu_vnt"] = p.get("isoriniu_kampu_vnt", 0) or 0
        merged["vidiniu_kampu_vnt"] = p.get("vidiniu_kampu_vnt", 0) or 0
        merged["doors"] = p.get("doors", [])
        merged["langai"] = p.get("langai", [])
        merged["gkp_nisos_pertvaru"] = p.get("gkp_nisos", [])
        merged["arkos_ar_puslankiai"] = p.get("arkos_ar_puslankiai", [])

    # --- Išklotinės — merge all sections from all pages ---
    iskl_list = grouped.get("išklotinė", [])
    all_sections = []
    for page_data in iskl_list:
        all_sections.extend(page_data.get("wall_sections", []))
    merged["wall_sections"] = all_sections

    # Calculate paint and tile areas from sections
    paint_m2 = 0.0
    tile_m2 = 0.0
    for sec in all_sections:
        for zone in sec.get("zones", []):
            area = zone.get("plotas_m2") or 0
            if zone.get("tipas") in ("dažymas", "dazymas"):
                paint_m2 += area
            elif zone.get("tipas") in ("plytelės", "plyteles"):
                tile_m2 += area
    if all_sections:
        merged["sienos_dazomas_m2_is_iskl"] = round(paint_m2, 2)
        merged["sienos_plyteles_m2_is_iskl"] = round(tile_m2, 2)

    # --- Lubų planas (ceiling) — aggregate ---
    lubu_list = grouped.get("lubų", [])
    if lubu_list:
        gkp_std = sum(p.get("gkp_plotas_standartinis_m2") or 0 for p in lubu_list)
        gkp_virs3 = sum(p.get("gkp_plotas_virs_3m_m2") or 0 for p in lubu_list)
        nisos_led = sum(p.get("nisos_led_m") or 0 for p in lubu_list)
        difuzoriai = {"apvalus": 0, "plysiniai": 0}
        sviestuvu = 0
        reviziniu: list = []
        for p in lubu_list:
            d = p.get("difuzoriu_skaicius") or {}
            difuzoriai["apvalus"] += d.get("apvalus") or 0
            difuzoriai["plysiniai"] += d.get("plysiniai") or 0
            sviestuvu += p.get("sviestuvu_skaicius") or 0
            reviziniu.extend(p.get("reviziniu_dureliu") or [])
        merged["gkp_lubu_standartinis_m2"] = round(gkp_std, 2)
        merged["gkp_lubu_virs3m_m2"] = round(gkp_virs3, 2)
        merged["nisos_led_m"] = round(nisos_led, 2)
        merged["difuzoriu_skaicius"] = difuzoriai
        merged["sviestuvu_skaicius"] = sviestuvu
        merged["reviziniu_dureliu"] = reviziniu

    # --- Grindų planas ---
    grind_list = grouped.get("grindų", [])
    if grind_list:
        merged["parketlentes_m2"] = round(sum(p.get("parketlentes_m2") or 0 for p in grind_list), 2)
        merged["plyteles_grindyse_m2"] = round(sum(p.get("plyteles_grindyse_m2") or 0 for p in grind_list), 2)
        merged["pvc_grindys_m2"] = round(sum(p.get("pvc_grindys_m2") or 0 for p in grind_list), 2)
        merged["terasa_m2"] = round(sum(p.get("terasa_m2") or 0 for p in grind_list), 2)
        # Grindjuostės — aggregate by type
        gj: dict[str, float] = {}
        for p in grind_list:
            for entry in p.get("grindjuosciu_tipai") or []:
                t = entry.get("tipas", "paprastos")
                gj[t] = gj.get(t, 0) + (entry.get("ilgis_m") or 0)
        merged["grindjuostiu_tipai"] = [{"tipas": t, "ilgis_m": round(v, 1)} for t, v in gj.items()]
        rastas = next((p.get("parketlentes_rastas") for p in grind_list if p.get("parketlentes_rastas")), None)
        if rastas:
            merged["parketlentes_rastas"] = rastas

    # --- Santechnikos planas ---
    sant_list = grouped.get("santechnikos", [])
    if sant_list:
        plumbing_keys = [
            "wc_remai_vnt", "wc_remai_ileidziami_sienon_vnt",
            "praustuvu_maisytuvai_potinkiniai_vnt", "dusu_maisytuvai_potinkiniai_vnt",
            "vonios_maisytuvai_vnt", "bide_dusiukai_vnt",
            "skalbimo_masinos_sifonai_vnt", "gyvatukai_vnt",
            "lauko_ciaupai_vnt", "trapai_lanakai_vnt", "kondicionieriu_trasos_vnt",
        ]
        for k in plumbing_keys:
            merged[k] = sum(p.get(k) or 0 for p in sant_list)

    # --- Elektros/rozecių + apšvietimo ---
    elec_list = grouped.get("rozecių", []) + grouped.get("apšvietimo", [])
    if elec_list:
        elec_keys = [
            "rozetes_vnt", "jungikliai_vnt", "rozetes_jungikliai_total_vnt",
            "sviestuvu_iskaiciai_vnt", "lauko_rozetes_vnt",
            "trifazes_rozetes_vnt", "signalizacijos_davikliu_vnt",
        ]
        for k in elec_keys:
            merged[k] = sum(p.get(k) or 0 for p in elec_list)
        merged["led_juostos_m"] = round(sum(p.get("led_juostos_m") or 0 for p in elec_list), 2)

    # --- Derive plyteliu_plotas_m2 (total tiles) ---
    grindys_tiles = merged.get("plyteles_grindyse_m2", 0)
    sienos_tiles = merged.get("sienos_plyteles_m2_is_iskl", 0)
    merged["plyteliu_plotas_m2"] = round(grindys_tiles + sienos_tiles, 2)

    return merged
