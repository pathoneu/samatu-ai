"""Throwaway: simulate the "Vision enumerated the LED rooms — don't infer
niches into the others" gate, per project, against the saved extracts.

Rule under test (fails closed):
  IF some warning mentions LED/nišos AND contains an explicit room-number
  list ("kambariuose 01, 03, 04, 05")
  THEN drop every nisa_LED whose _source == "statistical_inference" from
       rooms NOT in that list.
  ELSE change nothing.
"""
import sys, json, copy, pathlib, re, io, contextlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
import eval_harness as EH  # noqa: E402

LED_CTX = re.compile(r"led|niš|nis[ų]", re.IGNORECASE)
ROOM_LIST = re.compile(r"kambari(?:uose|ai|ų)\s*((?:\d+[.\d]*\s*,\s*)+\d+[.\d]*)",
                       re.IGNORECASE)


def enumerated_rooms(parsed):
    for w in parsed.get("warnings") or []:
        text = w.get("message") if isinstance(w, dict) else str(w)
        if not text or not LED_CTX.search(text):
            continue
        m = ROOM_LIST.search(text)
        if m:
            return {x.strip() for x in m.group(1).split(",")}, text
    return None, None


def apply_gate(parsed):
    allowed, src = enumerated_rooms(parsed)
    if not allowed:
        return parsed, None, []
    dropped = []
    for r in parsed.get("patalpos") or []:
        nr = str(r.get("nr") or "").strip()
        if nr in allowed:
            continue
        keep = []
        for e in r.get("elementai") or []:
            if ((e.get("tipas") or "").lower() == "nisa_led"
                    and e.get("_source") == "statistical_inference"):
                dropped.append((nr, r.get("pavadinimas"), e.get("ilgis_m")))
                continue
            keep.append(e)
        r["elementai"] = keep
    return parsed, src, dropped


for slug in ["objektas_a", "objektas_b", "objektas_c", "objektas_d"]:
    raw = json.loads((ROOT / f"ground_truth/{slug}/ai_extract.json")
                     .read_text(encoding="utf-8"))
    out = {}
    for label, gate in (("BEFORE", False), ("AFTER", True)):
        p = copy.deepcopy(raw)
        src = None
        dropped = []
        if gate:
            p, src, dropped = apply_gate(p)
        with contextlib.redirect_stdout(io.StringIO()):
            p = EH._rerun_deterministic_tail(p, slug)
        res = EH.evaluate(p, EH._load_truth(slug))
        scored, _, _ = EH._partition_headline_metrics(res, "ai_extract")
        mae = sum(abs(r.pct_error) for r in scored) / len(scored)
        led = next((r for r in scored if "LED" in r.label), None)
        out[label] = (mae, led.actual_value if led else None,
                      led.pct_error if led else None, src, dropped)
    b, a = out["BEFORE"], out["AFTER"]
    print(f"\n=== {slug}")
    print(f"  BEFORE  MAE={b[0]:7.3f}%   LED={b[1]}  ({b[2]:+.2f}%)")
    print(f"  AFTER   MAE={a[0]:7.3f}%   LED={a[1]}  ({a[2]:+.2f}%)")
    if a[3]:
        print(f"  gate fired on warning: {a[3][:100]}")
        for d in a[4]:
            print(f"    dropped inferred niche: room {d[0]} {d[1]} = {d[2]} m")
    else:
        print("  gate did NOT fire (no enumerating LED warning) — unchanged")
