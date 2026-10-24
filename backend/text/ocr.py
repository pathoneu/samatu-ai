"""Local OCR for sheets with no usable text layer (plan 2026-10-24 §3.2 `ocr.py`, R6, §9 Phase 1 cause 7).

objektas_c draws its dimension strings as outlines, objektas_j4 converted every letter to outlines, objektas_j3
is a scan: the text layer holds nothing the readers can use, so the sheet has no scale, no badges, no table.
This module reads the RENDER instead — on this machine (R6: no drawing leaves it; there is no cloud client
here and a guard test greps for one).

Interface: `ocr_words(image) -> list[Word]` with Word(text, x0, y0, x1, y1, conf, angle). Coordinates are the
image's pixels times `pt_per_px` — `ocr_page` renders a sheet in the DISPLAY frame (/Rotate applied, PDF points
from the top-left), the frame every text-layer reader yields its boxes in. `angle` is the direction the text
reads, counter-clockwise in degrees on the display: 0 normal, 90 reading upward (a vertical dimension string),
180 upside down, 270 reading downward. A lone word read vertically is reported as 90: whether it reads up or
down does not change its box or its text, and nothing downstream depends on it.

Rotated strings: the engine runs on the 0° render and on the render turned 90° clockwise (text reading upward
is upright there), and the two reads are de-duplicated — the read in which the engine saw the text upright wins,
then the higher confidence.

`page_items(words, …)` turns words into exactly what `extractor.plan_area_annotations._iter_pages` yields —
(page, W, H, chars, to_display), one item per text direction, chars in the frame where they read left to right —
so the dimension reader, the stated-scale rule and the badge rule consume OCR without a line changed.

Engines are pluggable (`SAMATU_OCR_ENGINE`): `rapid` (RapidOCR on onnxruntime with the PP-OCRv6 medium detector
and the Lithuanian recogniser — the PaddleOCR models without PaddlePaddle, which has no wheel for the Python the
backend runs on), `paddle` (PaddleOCR 3), `tesseract` (pytesseract + `lit` traineddata). Measured comparison:
docs/superpowers/research/2026-10-24-text-ocr.md. Every engine is imported lazily; none is a backend
requirement until the manager decides. Nothing here runs unless `SAMATU_OCR` is on (`ocr_enabled`).
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Sequence

log = logging.getLogger("samatu.text.ocr")

ENGINE_ENV = "SAMATU_OCR_ENGINE"
DPI_ENV = "SAMATU_OCR_DPI"
DEFAULT_ENGINE = "rapid"
DEFAULT_DPI = 300
ROTATIONS = (0, 90)
MIN_CONF = 0.5              # the engines' own default threshold; below it a read is noise
VERTICAL_RATIO = 1.5        # PP-OCR turns a crop taller than 1,5× its width before reading it (same rule)
SAME_WORD_SHARE = 0.5       # two reads covering this share of the smaller box are one word read twice
CACHE_PAGES = 64
MAX_SIDE_PX = 12000         # > an A1 sheet at 300 DPI (9933 px)


# Letters the Lithuanian alphabet does not have, read where the drawing has its look-alike: the recogniser's
# dictionary covers French and German too, and on small or rasterised type it reads ė as é and ū as ü
# (measured on objektas_a's flattened sheets and the j3 scan: most wrong diacritics were exactly these). Only
# one-to-one pairs; Ú (Ų or Ū?) and j / į are ambiguous and stay as read.
LT_LOOKALIKES = str.maketrans({"é": "ė", "è": "ė", "ê": "ė", "É": "Ė", "È": "Ė", "Ê": "Ė",
                               "ü": "ū", "û": "ū", "Ü": "Ū", "Û": "Ū"})


def lt_letters(text: str) -> str:
    return str(text).translate(LT_LOOKALIKES)


class OcrUnavailable(RuntimeError):
    """The chosen engine is not installed on this machine."""


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float
    angle: int


@dataclass
class Line:
    """One engine read in the pixel frame of the image it was given: the text, its quadrilateral, the
    engine's confidence, and — when the engine gives them — the word boxes inside it [(text, quad)]."""
    text: str
    quad: Sequence[Sequence[float]]
    conf: float
    words: list[tuple[str, Sequence[Sequence[float]]]] | None = None
    angle: int | None = None        # when the engine knows the reading direction itself (Tesseract: 0)


class Engine(Protocol):
    name: str

    def read(self, rgb) -> list[Line]: ...


# ── the flag ────────────────────────────────────────────────────────────────

def ocr_enabled() -> bool:
    """`SAMATU_OCR` (feature_flags, default OFF). OFF: no engine is created, no page is rendered for OCR."""
    from extractor.feature_flags import get_flags
    return bool(get_flags().get("ocr"))


# ── engines ─────────────────────────────────────────────────────────────────

MODEL_DIR_ENV = "SAMATU_OCR_MODEL_DIR"
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[1] / "data" / "models" / "ocr"   # backend/data/models/ocr (gitignored)
# The three models RapidEngine runs, as RapidOCR names them (its default_models.yaml routes them to one file each):
# (task, OCR version, model size, language). `model_files()` turns them into file names, URLs and SHA-256 sums.
RAPID_MODELS = (("det", "PP-OCRv6", "medium", "lt"), ("rec", "PP-OCRv6", "medium", "lt"),
                ("cls", "PP-OCRv4", "mobile", "ch"))


def model_dir() -> Path:
    return Path(os.environ.get(MODEL_DIR_ENV) or DEFAULT_MODEL_DIR)


def _production() -> bool:
    """The same test main.py uses for its production hardening."""
    return (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower() in ("prod", "production")


def model_files() -> dict[str, dict]:
    """{task: {file, url, sha256}} of RAPID_MODELS — from RapidOCR's own model table, so the fetch script and the
    engine can never disagree about which file a model is."""
    from rapidocr.inference_engine.base import FileInfo, InferSession
    from rapidocr.utils.typings import EngineType, ModelType, OCRVersion, TaskType
    out = {}
    for task, version, size, lang in RAPID_MODELS:
        info = InferSession.get_model_url(FileInfo(EngineType("onnxruntime"), OCRVersion(version), TaskType(task),
                                                   lang, ModelType(size)))
        url = str(info["model_dir"])
        out[task] = {"file": url.rsplit("/", 1)[-1], "url": url, "sha256": info.get("SHA256")}
    return out


def engine_version() -> str:
    """What a cached OCR result depends on besides the sheet: the engine, its library version, the models."""
    try:
        from importlib.metadata import version
        lib = version("rapidocr")
    except Exception:  # noqa: BLE001
        lib = "?"
    return f"rapid-{lib}-" + "-".join(f"{v}{s}" for _t, v, s, _l in RAPID_MODELS)


class RapidEngine:
    """RapidOCR (onnxruntime) with PP-OCRv6 medium: the detector, and the recogniser for Lithuanian (`lt`).

    Models: from `model_dir()` (`scripts/fetch_ocr_models.py` puts them there at image build). When a file is
    missing, production refuses (OcrUnavailable — never a download while a person waits); elsewhere RapidOCR
    downloads it into that same directory (SHA-256 checked) on first use."""
    name = "rapid"

    def __init__(self) -> None:
        try:
            from rapidocr import ModelType, OCRVersion, RapidOCR
        except ImportError as e:  # pragma: no cover — depends on the machine
            raise OcrUnavailable("rapidocr is not installed") from e
        v6, medium = OCRVersion("PP-OCRv6"), ModelType("medium")
        params = {
            "Rec.lang_type": "lt", "Rec.ocr_version": v6, "Rec.model_type": medium,
            "Det.ocr_version": v6, "Det.model_type": medium, "Global.log_level": "error",
            # RapidOCR shrinks any image to 2000 px on its long side before detecting: a 300 DPI A3 sheet becomes
            # ~100 DPI and 2 mm dimension digits vanish. A drawing is read at the resolution it was rendered at.
            "Global.max_side_len": MAX_SIDE_PX,
        }
        d = model_dir()
        files = model_files()
        missing = [f["file"] for f in files.values() if not (d / f["file"]).is_file()]
        if not missing:
            params.update({f"{t.capitalize()}.model_path": str(d / f["file"]) for t, f in files.items()})
        elif _production():
            raise OcrUnavailable(f"OCR models missing in {d}: {', '.join(missing)} — run scripts/fetch_ocr_models.py "
                                 f"at image build")
        else:
            d.mkdir(parents=True, exist_ok=True)
            params["Global.model_root_dir"] = str(d)
        self._eng = RapidOCR(params=params)
        self._lock = threading.Lock()

    def read(self, rgb) -> list[Line]:
        with self._lock:
            r = self._eng(rgb, return_word_box=True)
        if not r or r.txts is None:
            return []
        out = []
        wrs = list(r.word_results) if r.word_results and len(r.word_results) == len(r.txts) else [None] * len(r.txts)
        for txt, sc, box, wr in zip(r.txts, r.scores, r.boxes, wrs):
            words = [(str(w[0]), w[2]) for w in wr if w and w[2] is not None] if wr else None
            out.append(Line(str(txt), [list(map(float, p)) for p in box], float(sc), words or None))
        return out


class PaddleEngine:
    """PaddleOCR 3 (PaddlePaddle), lang `lt` — the reference the RapidOCR port is measured against."""
    name = "paddle"

    def __init__(self) -> None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as e:  # pragma: no cover
            raise OcrUnavailable("paddleocr is not installed") from e
        self._eng = PaddleOCR(lang="lt", use_doc_orientation_classify=False, use_doc_unwarping=False,
                              use_textline_orientation=True)
        self._lock = threading.Lock()

    def read(self, rgb) -> list[Line]:
        with self._lock:
            res = self._eng.predict(rgb, return_word_box=True)
        out = []
        for r in res or []:
            j = r.json.get("res", r.json) if hasattr(r, "json") else r
            texts, scores, polys = j.get("rec_texts") or [], j.get("rec_scores") or [], j.get("rec_polys") or []
            tw, tr = j.get("text_word") or [None] * len(texts), j.get("text_word_region") or [None] * len(texts)
            for i, (txt, sc, poly) in enumerate(zip(texts, scores, polys)):
                words = None
                if i < len(tw) and tw[i] and i < len(tr) and tr[i] and len(tw[i]) == len(tr[i]):
                    words = _merge_char_words(tw[i], tr[i])
                out.append(Line(str(txt), [list(map(float, p)) for p in poly], float(sc), words))
        return out


def _merge_char_words(tokens, regions) -> list[tuple[str, list]] | None:
    """PaddleOCR's word boxes come as tokens (often single characters) — join them into space-separated words."""
    words: list[tuple[str, list]] = []
    cur_t, cur_pts = "", []
    for t, reg in zip(tokens, regions):
        t = str(t)
        if not t.strip():
            if cur_t:
                words.append((cur_t, cur_pts))
            cur_t, cur_pts = "", []
            continue
        cur_t += t
        cur_pts += [list(map(float, p)) for p in reg]
    if cur_t:
        words.append((cur_t, cur_pts))
    out = []
    for t, pts in words:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        out.append((t, [[min(xs), min(ys)], [max(xs), min(ys)], [max(xs), max(ys)], [min(xs), max(ys)]]))
    return out or None


class TesseractEngine:
    """Tesseract 5 through pytesseract, `lit+eng`, sparse text (psm 11). Reads upright text only — the 90° pass
    is what gives it vertical strings. `TESSDATA_PREFIX` must hold lit.traineddata."""
    name = "tesseract"

    def __init__(self) -> None:
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
        except Exception as e:  # pragma: no cover
            raise OcrUnavailable("tesseract is not installed") from e
        self._pt = pytesseract

    def read(self, rgb) -> list[Line]:
        from PIL import Image
        d = self._pt.image_to_data(Image.fromarray(rgb), lang="lit+eng", config="--psm 11",
                                   output_type=self._pt.Output.DICT)
        out = []
        for i, txt in enumerate(d["text"]):
            t = str(txt or "").strip()
            conf = float(d["conf"][i])
            if not t or conf < 0:
                continue
            x, y, w, h = (float(d[k][i]) for k in ("left", "top", "width", "height"))
            out.append(Line(t, [[x, y], [x + w, y], [x + w, y + h], [x, y + h]], conf / 100.0, None, angle=0))
        return out


_ENGINE_TYPES = {"rapid": RapidEngine, "paddle": PaddleEngine, "tesseract": TesseractEngine}
_engines: dict[str, Engine] = {}
_engines_lock = threading.Lock()


def engine_name() -> str:
    return (os.environ.get(ENGINE_ENV) or DEFAULT_ENGINE).strip().lower()


def get_engine(name: str | None = None) -> Engine:
    """The process's engine of that name (created once — model load takes seconds)."""
    name = (name or engine_name()).strip().lower()
    if name not in _ENGINE_TYPES:
        raise OcrUnavailable(f"unknown OCR engine {name!r} (rapid | paddle | tesseract)")
    with _engines_lock:
        if name not in _engines:
            _engines[name] = _ENGINE_TYPES[name]()
        return _engines[name]


def ocr_dpi() -> int:
    try:
        return max(72, min(600, int(os.environ.get(DPI_ENV) or DEFAULT_DPI)))
    except ValueError:
        return DEFAULT_DPI


# ── geometry of one read ────────────────────────────────────────────────────

def _bbox(quad) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in quad]
    ys = [float(p[1]) for p in quad]
    return min(xs), min(ys), max(xs), max(ys)


def _unrotate(u: float, v: float, r: int, w: float, h: float) -> tuple[float, float]:
    """A point of the image turned `r`° CLOCKWISE back into the original w × h image."""
    if r == 90:
        return v, h - u
    if r == 180:
        return w - u, h - v
    if r == 270:
        return w - v, u
    return u, v


def _rotate_image(rgb, r: int):
    import numpy as np
    return np.ascontiguousarray(np.rot90(rgb, -(r // 90))) if r % 360 else rgb


def _split_words(line: Line, vertical: bool) -> list[tuple[str, tuple[float, float, float, float]]]:
    """The line's words with their boxes (image frame). The engine's own word boxes when it gives them; else the
    line's box divided along its reading axis in proportion to the characters (a space counts as one)."""
    if line.words:
        return [(t, _bbox(q)) for t, q in line.words if str(t).strip()]
    x0, y0, x1, y1 = _bbox(line.quad)
    parts = line.text.split()
    if len(parts) <= 1:
        return [(line.text.strip(), (x0, y0, x1, y1))] if line.text.strip() else []
    n = len(line.text)
    out, pos = [], 0
    for p in parts:
        start = line.text.index(p, pos)
        pos = start + len(p)
        a, b = start / n, pos / n
        if vertical:        # read upward: the first character at the bottom
            out.append((p, (x0, y1 - b * (y1 - y0), x1, y1 - a * (y1 - y0))))
        else:
            out.append((p, (x0 + a * (x1 - x0), y0, x0 + b * (x1 - x0), y1)))
    return out


def _local_angle(line: Line, words: list[tuple[str, tuple]], vertical: bool) -> int:
    """Reading direction of a line in the image it was read from: the word order tells up from down and
    left-to-right from upside-down; a lone word keeps the engine's default (0, or 90 when vertical)."""
    if line.angle is not None:
        return int(line.angle) % 360
    if len(words) >= 2:
        (_, a), (_, b) = words[0], words[-1]
        if vertical:
            return 270 if (a[1] + a[3]) < (b[1] + b[3]) else 90
        return 180 if (a[0] + a[2]) > (b[0] + b[2]) else 0
    return 90 if vertical else 0


def _overlap_share(a: Word, b: Word) -> float:
    ix = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    iy = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    small = min((a.x1 - a.x0) * (a.y1 - a.y0), (b.x1 - b.x0) * (b.y1 - b.y0))
    return ix * iy / small if small > 0 else 0.0


def ocr_words(image, engine: Engine | None = None, pt_per_px: float | tuple[float, float] = 1.0,
              rotations: Iterable[int] = ROTATIONS, min_conf: float = MIN_CONF) -> list[Word]:
    """Every word the engine reads on `image` (PIL image or RGB array), in the image's frame × `pt_per_px`
    (a number, or (x, y) factors). Reads at each rotation are merged (module doc)."""
    import numpy as np
    rgb = np.asarray(image.convert("RGB")) if hasattr(image, "convert") else np.asarray(image)
    h, w = rgb.shape[:2]
    sx, sy = (pt_per_px, pt_per_px) if isinstance(pt_per_px, (int, float)) else pt_per_px
    eng = engine or get_engine()
    reads: list[tuple[bool, Word]] = []
    for r in rotations:
        r = int(r) % 360
        for line in eng.read(_rotate_image(rgb, r)):
            if line.conf < min_conf:
                continue
            lx0, ly0, lx1, ly1 = _bbox(line.quad)
            vertical = line.angle is None and (ly1 - ly0) >= VERTICAL_RATIO * (lx1 - lx0)
            words = _split_words(line, vertical)
            local = _local_angle(line, words, vertical)
            for text, (x0, y0, x1, y1) in words:
                pts = [_unrotate(u, v, r, w, h) for u, v in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                reads.append((local == 0, Word(text=lt_letters(text), x0=min(xs) * sx, y0=min(ys) * sy, x1=max(xs) * sx,
                                               y1=max(ys) * sy, conf=round(float(line.conf), 4),
                                               angle=(r + local) % 360)))
    # one word read twice (both passes; or an engine's overlapping boxes): the upright read, then confidence
    reads.sort(key=lambda t: (not t[0], -t[1].conf))
    kept: list[Word] = []
    for _, wd in reads:
        if any(_overlap_share(wd, k) >= SAME_WORD_SHARE for k in kept):
            continue
        kept.append(wd)
    kept.sort(key=lambda wd: (wd.y0, wd.x0))
    return [_tighten(wd, rgb, sx, sy) for wd in kept]


# PP-OCR pads every detected box (its unclip ratio): measured 2026-10-24 on the renders of objektas_c, j3, j4, the ink
# inside an OCR word box is only 0,59–0,66 of its height (median), ~1,9 pt of padding above and 1,2–1,7 pt below.
# Every text-layer rule downstream is tuned in points on tight glyph boxes — a badge's height, „another number
# touching it" within 1,2 heights, table rows 14 pt apart — so a padded box makes a badge look taller and its
# neighbours nearer (j3: room 6's badge read as touching the dimension „4250" 9,9 pt away). Each word is therefore
# cut to the ink it covers on the render. Rows (columns, for a vertical word) inked across ≥ LINE_SHARE of the box
# are a line running through the padding — a dimension line under the digits — and are not the word's ink.
LINE_SHARE = 0.85
MIN_TIGHT_SHARE = 0.25      # a cut leaving less than this of the box is noise, not the word: keep the box as read


def _tighten(wd: Word, rgb, sx: float, sy: float) -> Word:
    import numpy as np
    H, W = rgb.shape[:2]
    x0, y0 = max(0, int(wd.x0 / sx)), max(0, int(wd.y0 / sy))
    x1, y1 = min(W, int(np.ceil(wd.x1 / sx))), min(H, int(np.ceil(wd.y1 / sy)))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return wd
    box = rgb[y0:y1, x0:x1]
    ink = (box.min(axis=2) if box.ndim == 3 else box) < 150
    if not ink.any():
        return wd
    rows, cols = ink.mean(axis=1), ink.mean(axis=0)
    r = np.where((rows > 0) & (rows < LINE_SHARE))[0]
    c = np.where((cols > 0) & (cols < LINE_SHARE))[0]
    if len(r) < 2 or len(c) < 2:
        return wd
    t, b, l, rr = int(r[0]), int(r[-1]) + 1, int(c[0]), int(c[-1]) + 1
    if (b - t) < MIN_TIGHT_SHARE * (y1 - y0) or (rr - l) < MIN_TIGHT_SHARE * (x1 - x0):
        return wd
    return Word(text=wd.text, x0=(x0 + l) * sx, y0=(y0 + t) * sy, x1=(x0 + rr) * sx, y1=(y0 + b) * sy,
                conf=wd.conf, angle=wd.angle)


# ── a PDF sheet ─────────────────────────────────────────────────────────────

_cache: "OrderedDict[tuple, tuple[float, float, list[Word]]]" = OrderedDict()
_cache_lock = threading.Lock()


def render_page(pdf_bytes: bytes, page: int, dpi: int):
    """(PIL image in the display frame, Wd, Hd) of a 1-based page."""
    import pypdfium2 as pdfium

    from extractor.pdf_vectors import page_frames
    from extractor.pdfium_guard import PDFIUM_LOCK
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            pg = doc[int(page) - 1]
            try:
                _W, _H, Wd, Hd, _rot = page_frames(pg)
                img = pg.render(scale=dpi / 72.0).to_pil().convert("RGB")
            finally:
                pg.close()
        finally:
            doc.close()
    return img, Wd, Hd


# ── the disk cache: a sheet is OCR'd once, not on every click ──────────────
# One JSON file per (PDF content hash, page, DPI, engine + library + model versions, rotations) under
# `cache_dir()` (backend/data/ocr_cache, gitignored; SAMATU_OCR_CACHE_DIR overrides). The content hash IS the
# project's drawing: a re-upload of the same PDF reuses it, a changed PDF never does. 10–30 s of OCR per sheet
# becomes a ~5 ms read. Only the built-in engines are cached on disk (a test's fake engine stays in memory).
CACHE_DIR_ENV = "SAMATU_OCR_CACHE_DIR"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "ocr_cache"
CACHE_FORMAT = 2          # 2: word boxes cut to their ink (_tighten)


def cache_dir() -> Path:
    return Path(os.environ.get(CACHE_DIR_ENV) or DEFAULT_CACHE_DIR)


def _engine_tag(eng) -> str | None:
    """The engine's part of the disk key, or None when the engine is not a built-in one (no disk cache)."""
    if type(eng) is RapidEngine:
        return engine_version()
    if type(eng) in (PaddleEngine, TesseractEngine):
        return eng.name
    return None


def _disk_path(digest: str, page: int, dpi: int, tag: str, rot: tuple) -> Path:
    name = hashlib.sha1(f"{CACHE_FORMAT}|{digest}|{page}|{dpi}|{tag}|{rot}".encode()).hexdigest()
    return cache_dir() / digest[:2] / f"{digest[:16]}-p{page}-{name[:12]}.json"


def _disk_read(path: Path) -> tuple[float, float, list[Word]] | None:
    import json
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        return float(rec["Wd"]), float(rec["Hd"]), [Word(**w) for w in rec["words"]]
    except FileNotFoundError:
        return None
    except Exception:  # noqa: BLE001 — a torn or old file is a miss, never a failure
        log.warning("OCR cache unreadable: %s", path)
        return None


def _disk_write(path: Path, out: tuple[float, float, list[Word]], meta: dict) -> None:
    import json
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps({**meta, "Wd": out[0], "Hd": out[1],
                                   "words": [w.__dict__ for w in out[2]]}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception:  # noqa: BLE001 — a read-only disk only costs the next call its OCR
        log.warning("OCR cache not written: %s", path, exc_info=True)


def ocr_page(pdf_bytes: bytes, page: int, dpi: int | None = None, engine: Engine | None = None,
             rotations: Iterable[int] = ROTATIONS) -> tuple[float, float, list[Word]]:
    """(Wd, Hd, words) of a sheet, display frame, PDF points. Cached per (file, page, dpi, engine, rotations):
    in memory, and on disk for the built-in engines (above)."""
    dpi = int(dpi or ocr_dpi())
    eng = engine or get_engine()
    rot = tuple(int(r) % 360 for r in rotations)
    digest = hashlib.sha1(pdf_bytes).hexdigest()
    key = (digest, int(page), dpi, getattr(eng, "name", type(eng).__name__), rot)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    tag = _engine_tag(eng)
    path = _disk_path(digest, int(page), dpi, tag, rot) if tag else None
    out = _disk_read(path) if path else None
    if out is None:
        import time
        t0 = time.time()
        img, Wd, Hd = render_page(pdf_bytes, page, dpi)
        words = ocr_words(img, eng, (Wd / img.width, Hd / img.height), rot)
        out = (Wd, Hd, words)
        if path:
            _disk_write(path, out, {"format": CACHE_FORMAT, "engine": tag, "dpi": dpi, "page": int(page),
                                    "rotations": list(rot), "seconds": round(time.time() - t0, 2)})
    with _cache_lock:
        _cache[key] = out
        while len(_cache) > CACHE_PAGES:
            _cache.popitem(last=False)
    return out


# ── words → the text-layer readers' shape ──────────────────────────────────

def _chars_of(word: Word, tk: int, Wd: float, Hd: float) -> list[dict]:
    from extractor.plan_area_annotations import _turn_box
    x0, top, x1, bottom = _turn_box([word.x0, word.y0, word.x1, word.y1], tk, Wd, Hd) if tk else (
        word.x0, word.y0, word.x1, word.y1)
    n = max(1, len(word.text))
    step = (x1 - x0) / n
    size = max(bottom - top, 1.0)
    return [{"text": ch, "x0": x0 + i * step, "x1": x0 + (i + 1) * step, "top": top, "bottom": bottom,
             "size": size, "ocr_conf": word.conf} for i, ch in enumerate(word.text)]


def page_items(words: Sequence[Word], page: int, Wd: float, Hd: float) -> list[tuple]:
    """What `plan_area_annotations._iter_pages` yields for a page, built from OCR words: one item per reading
    direction, (page, Wd, Hd, chars, to_display) — chars {text, x0, x1, top, bottom, size} in the frame where
    they read left to right (each word's box split evenly into its characters), `to_display` mapping a box in
    that frame back to the display frame."""
    from extractor.plan_area_annotations import _identity, _turn_box
    by_turn: dict[int, list[dict]] = {}
    for wd in words:
        tk = (int(wd.angle) // 90) % 4          # text at k·90° CCW needs k clockwise quarter turns to read
        by_turn.setdefault(tk, []).extend(_chars_of(wd, tk, Wd, Hd))
    out = []
    for tk in sorted(by_turn, key=lambda k: (k != 0, -len(by_turn[k]))):
        Wa, Ha = (Hd, Wd) if tk in (1, 3) else (Wd, Hd)

        def to_display(bbox, tk=tk, Wa=Wa, Ha=Ha):
            return _turn_box(list(bbox), (4 - tk) % 4, Wa, Ha)
        out.append((int(page), Wd, Hd, by_turn[tk], to_display if tk else _identity))
    return out


def ocr_page_items(pdf_bytes: bytes, page: int, dpi: int | None = None, engine: Engine | None = None) -> list[tuple]:
    Wd, Hd, words = ocr_page(pdf_bytes, page, dpi, engine)
    return page_items(words, page, Wd, Hd)


def dimension_strings(pdf_bytes: bytes, page: int, dpi: int | None = None,
                      engine: Engine | None = None, units: str = "mm") -> tuple[list[dict], set[int]]:
    """(dimension strings, written scales) OCR finds on a sheet — the line reader's own parsing
    (`plan_dimensions._dimensions_on_page`, `stated_scales_on_page`) over OCR characters. Each string is marked
    `source: "ocr"` with the word's confidence; none has a hairline (`span_source`). `units="cm"`: integers read as
    centimetres (geometry/scale.py decides which reading the sheet measures). A string starting with 0 is dropped
    in both readings: a dimension never does, and the engine's systematic error — a short string printed upside
    down read without the flip („80" → „08", „690" → „069") — always does (research doc 2026-10-24-text-ocr §1)."""
    from extractor.plan_dimensions import _dimensions_on_page, stated_scales_on_page
    Wd, Hd, words = ocr_page(pdf_bytes, page, dpi, engine)
    dims: list[dict] = []
    stated: set[int] = set()
    for pn, W_, H_, chars, to_display in page_items(words, page, Wd, Hd):
        stated |= stated_scales_on_page(chars)
        for d in _dimensions_on_page(pn, W_, H_, chars, to_display, units=units):
            if str(d["text"]).startswith("0"):
                continue
            x0, y0, x1, y1 = d["bbox"]
            box = Word(d["text"], x0, y0, x1, y1, 0.0, 0)
            confs = [w.conf for w in words if _overlap_share(box, w) >= SAME_WORD_SHARE]
            d["source"] = "ocr"
            d["ocr_conf"] = min(confs) if confs else None
            if units != "mm":
                d["units"] = units
            dims.append(d)
    return dims, stated


def detail_scales(pdf_bytes: bytes, page: int, dpi: int | None = None, engine: Engine | None = None) -> set[int]:
    """Detail scales („M 1:5", „1:10") the sheet writes — below the plan range `stated_scales_on_page` keeps. A sheet
    that writes one is never read as centimetres: its millimetres at 1:10 look exactly like centimetres at 1:100."""
    import re

    from extractor.plan_area_annotations import _line_text, _lines
    from extractor.plan_dimensions import _STANDARD_SCALES, MIN_SCALE_DENOM
    small = re.compile(r"(?<![\d.,:/])1\s*:\s*(\d{1,2})(?![\d.,:])")
    Wd, Hd, words = ocr_page(pdf_bytes, page, dpi, engine)
    out: set[int] = set()
    for _pn, _W, _H, chars, _ in page_items(words, page, Wd, Hd):
        for line in _lines(chars):
            for m in small.finditer(_line_text(line)):
                n = int(m.group(1))
                if n in _STANDARD_SCALES and n < MIN_SCALE_DENOM:
                    out.add(n)
    return out


def words_record(words: Sequence[Word]) -> list[dict]:
    """JSON-ready words (the spike scripts and any future cache)."""
    return [dict(text=w.text, x0=round(w.x0, 2), y0=round(w.y0, 2), x1=round(w.x1, 2), y1=round(w.y1, 2),
                 conf=w.conf, angle=w.angle) for w in words]


__all__ = ["Word", "Line", "Engine", "OcrUnavailable", "ocr_enabled", "get_engine", "engine_name", "ocr_dpi",
           "ocr_words", "ocr_page", "page_items", "ocr_page_items", "dimension_strings", "render_page",
           "words_record", "lt_letters"]
