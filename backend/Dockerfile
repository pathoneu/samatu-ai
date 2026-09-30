# Pathon backend — production image (Render `runtime: docker`, context = repo root).
#
# WHY DOCKER: the extraction pipeline hard-depends on native libraries that
# Render's plain `runtime: python` cannot install (no apt access):
#   - poppler-utils  → pdf2image (page rasterization in main.py, page_raster_cache,
#                      apdailos/door readers, agentic crop)
#   - libglib2.0-0   → opencv-python-headless (flood-fill / click-to-fill)
#   - libgl1         → headless cv2 wheels normally don't link libGL, but the
#                      only config proven in production (Railway nixpacks.toml)
#                      ships it — match that runtime, don't rediscover at 3am.
# Railway got these via nixpacks.toml; this image is the Render equivalent.
# Fonts are NOT needed from the system — DejaVu ships in backend/assets/fonts.
FROM python:3.14-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer-cache the dependency install.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
# prompts/ lives at repo root and is read via relative paths from backend/.
COPY prompts/ prompts/
# The FROZEN contractor-family → app-family concept table. It lives in scripts/
# because the harness owns it, but `extractor/row_scorecard` and
# `extractor/samata_template` load it by path, and the second of those runs
# behind /api/samata-templates. Without this the endpoint would degrade to
# blank cells in production only — the worst kind of difference from dev.
# (Railway's nixpacks build copies the whole repo, so it already had it.)
COPY scripts/reconcile_samata_lines.py scripts/reconcile_samata_lines.py
# Read-only report of files left by deleted projects. It has to run where the
# production database and side stores live, i.e. inside this container.
COPY scripts/report_orphaned_files.py scripts/report_orphaned_files.py

WORKDIR /app/backend

# --proxy-headers + --forwarded-allow-ips='*': request.client.host must reflect
# the real client behind Render's edge; the rate limiter additionally keys on
# the RIGHTMOST X-Forwarded-For hop (2026-07-15 hardening), so '*' here is safe.
CMD uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
