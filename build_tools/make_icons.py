"""Generate icon.ico (idle) and icon_rec.ico (recording, with red dot).

Run once at build time:  python build_tools/make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "src" / "resources"
OUT.mkdir(parents=True, exist_ok=True)


def _camera_glyph(size: int, recording: bool) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = max(1, size // 32)  # near-zero padding — glyph fills the canvas
    bump_h = size // 8         # small viewfinder bump
    bump_w = size // 3
    cx = size // 2

    # Viewfinder bump
    d.rounded_rectangle(
        (cx - bump_w // 2, pad, cx + bump_w // 2, pad + bump_h),
        radius=max(1, size // 40),
        fill=(40, 40, 48, 255),
    )

    # Main body — fills most of the canvas
    body = (pad, pad + bump_h, size - pad, size - pad)
    d.rounded_rectangle(
        body,
        radius=max(2, size // 16),
        fill=(40, 40, 48, 255),
        outline=(230, 230, 230, 255),
        width=max(1, size // 40),
    )

    # Lens (large, centered in body)
    bcx = (body[0] + body[2]) // 2
    bcy = (body[1] + body[3]) // 2
    r = min(body[2] - body[0], body[3] - body[1]) // 2 - max(1, size // 16)
    d.ellipse((bcx - r, bcy - r, bcx + r, bcy + r), fill=(230, 230, 230, 255))
    ir = int(r * 0.55)
    d.ellipse((bcx - ir, bcy - ir, bcx + ir, bcy + ir), fill=(60, 60, 60, 255))

    if recording:
        # Larger, bolder red dot in the top-right corner
        dr = max(3, size // 3)
        margin = max(1, size // 24)
        d.ellipse(
            (size - dr - margin, margin, size - margin, margin + dr),
            fill=(225, 30, 30, 255),
            outline=(255, 255, 255, 255),
            width=max(1, size // 40),
        )
    return img


def write_ico(path: Path, recording: bool) -> None:
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    big = _camera_glyph(256, recording)
    big.save(path, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"Wrote {path}  ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    write_ico(OUT / "icon.ico", recording=False)
    write_ico(OUT / "icon_rec.ico", recording=True)
