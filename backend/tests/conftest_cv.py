"""Generate synthetic room images for cv_polygon tests.

Deterministic — same output every time. Uses Pillow only (already in deps
via pdf2image). Two rooms:
  - synthetic_room_simple: 512x512, single 200x200 room with closed walls
    centered at (256, 256). Walls = solid black 4 px lines on white.
  - synthetic_room_with_door: same but with a 30-px gap in the south wall
    (door opening that morphological-close should bridge).
"""

from pathlib import Path
from PIL import Image, ImageDraw

ASSETS_DIR = Path(__file__).parent / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def _make_simple_room() -> None:
    path = ASSETS_DIR / "synthetic_room_simple.png"
    if path.exists():
        return
    img = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(img)
    # Outer building walls (avoid edge interaction)
    draw.rectangle([20, 20, 492, 492], outline="black", width=4)
    # Single inner room: 200x200 centered
    draw.rectangle([156, 156, 356, 356], outline="black", width=4)
    img.save(path)


def _make_room_with_door() -> None:
    path = ASSETS_DIR / "synthetic_room_with_door.png"
    if path.exists():
        return
    img = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 492, 492], outline="black", width=4)
    # Inner room with an 8-px door opening on the south wall (gap from x=248 to x=256).
    # 8 px is the realistic schematic-door width at 200 DPI; morph-close with
    # kernel ≥ 9 bridges it. Larger gaps would need kernel >= gap_width which
    # defeats the purpose of door gap-filling.
    draw.line([156, 156, 356, 156], fill="black", width=4)
    draw.line([156, 156, 156, 356], fill="black", width=4)
    draw.line([356, 156, 356, 356], fill="black", width=4)
    draw.line([156, 356, 248, 356], fill="black", width=4)
    draw.line([256, 356, 356, 356], fill="black", width=4)
    img.save(path)


def regenerate_synthetic_assets() -> None:
    _make_simple_room()
    _make_room_with_door()


# Auto-run on import so pytest discovery triggers asset creation.
regenerate_synthetic_assets()
