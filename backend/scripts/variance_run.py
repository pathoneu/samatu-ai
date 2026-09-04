"""One live Opus-4.8 extraction on Objektas A → key lines for variance analysis.
Usage: RUN_ID=2 python scripts/variance_run.py
Writes /tmp/opus48_objektas_a_run<RUN_ID>.json + prints the flagged lines."""
import sys, os, json, time
sys.path.insert(0, '.')
for line in open('.env'):
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1); os.environ.setdefault(k, v.strip().strip('"').strip("'"))

from extractor.vision_call import extract_interior

run_id = os.environ.get('RUN_ID', 'x')
pdf = open('../docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf', 'rb').read()
print(f"[run {run_id}] extracting…", flush=True)
t0 = time.time()
res = extract_interior(pdf)
print(f"[run {run_id}] done {time.time()-t0:.0f}s status={res.get('status')}", flush=True)
if res.get('status') != 'ok':
    print(f"[run {run_id}] ERROR:", res.get('_error')); sys.exit(1)
poz = res.get('pozicijos') or []
def oq(needle):
    for p in poz:
        if needle in (p.get('aprasymas') or '').lower():
            return p.get('kiekis')
    return None
key = {
    'paint_iki': oq('glaistymas/dažymas (iki'),
    'paint_virs': oq('glaistymas/dažymas (virš'),
    'led': oq('led juostos pajung'),
    'kampai': oq('dažymo kampų'),
    'angokrasciai': oq('angokraščių glaist'),
    'durys_beapvad': oq('beapvadinėms'),
    'rotband': oq('rotband'),
    'rooms': len(res.get('patalpos') or []),
    'n_poz': len(poz),
}
json.dump(res, open(f'/tmp/opus48_objektas_a_run{run_id}.json', 'w'), ensure_ascii=False)
print(f"[run {run_id}] KEY {json.dumps(key, ensure_ascii=False)}", flush=True)
