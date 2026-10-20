"""Generate sample images for comparing QR / barcode decoders.

Each image contains several 2D codes and barcodes placed on one canvas.
The expected decode results are written to ``samples/expected.json`` so that
``compare_decoders.py`` can score each decoder automatically.

Usage:
    python scripts/generate_samples.py
"""

import json
import random
from pathlib import Path

import segno
import zxingcpp
from PIL import Image, ImageDraw, ImageFilter

SAMPLES_DIR = Path(__file__).parent / "samples"
CANVAS_SIZE = (1800, 1100)
# Fixed seed so that the noisy image is identical on every run.
RANDOM_SEED = 42

# (kind, format label, content, encoding option)
# The format label uses zxing-cpp style names; the comparison script
# normalizes pyzbar names to the same vocabulary.
CODE_SPECS: list[dict] = [
    {
        "kind": "qr",
        "format": "QRCode",
        "text": "https://example.com/item?id=12345",
    },
    {
        "kind": "qr",
        "format": "QRCode",
        "text": "日本語テキスト：品番A-001 数量10",
        "encoding": "utf-8",
    },
    # Many Japanese QR codes in the field use Kanji mode (Shift_JIS), which
    # is a common source of garbled text, so it is tested apart from UTF-8.
    {
        "kind": "qr",
        "format": "QRCode",
        "text": "漢字モード試験",
        "mode": "kanji",
    },
    {"kind": "zx", "format": "Code128", "text": "LOT-2026-1018"},
    {"kind": "zx", "format": "EAN13", "text": "4901234567894"},
    {"kind": "zx", "format": "Code39", "text": "ABC-123"},
    {"kind": "zx", "format": "DataMatrix", "text": "DM:SERIAL-0001"},
]

# Layout positions (top-left) on the canvas, one per CODE_SPECS entry.
POSITIONS: list[tuple[int, int]] = [
    (60, 60),
    (560, 60),
    (1060, 60),
    (60, 560),
    (660, 560),
    (1260, 560),
    (60, 880),
]


def render_code(spec: dict) -> Image.Image:
    """Render one code described by ``spec`` as a grayscale PIL image.

    Args:
        spec: One entry of ``CODE_SPECS``.

    Returns:
        The rendered code with a quiet zone, in mode ``"L"``.

    Raises:
        ValueError: If ``spec["kind"]`` is unknown.
    """
    if spec["kind"] == "qr":
        qr = segno.make_qr(
            spec["text"],
            mode=spec.get("mode"),
            encoding=spec.get("encoding"),
            error="m",
        )
        return _segno_to_pil(qr)
    if spec["kind"] == "zx":
        fmt = getattr(zxingcpp.BarcodeFormat, spec["format"])
        barcode = zxingcpp.create_barcode(spec["text"], fmt)
        scale = 8 if spec["format"] == "DataMatrix" else 3
        img = Image.fromarray(barcode.to_image(scale=scale))
        # 1D barcodes are only one module tall; stretch them so they look like
        # real printed labels.
        if spec["format"] != "DataMatrix":
            img = img.resize((img.width, 220), Image.NEAREST)
        return img.convert("L")
    raise ValueError(f"unknown kind: {spec['kind']}")


def _segno_to_pil(qr: segno.QRCode) -> Image.Image:
    """Convert a segno QR code to a grayscale PIL image.

    Args:
        qr: QR code object created by segno.

    Returns:
        The QR code drawn with 8 px modules and a 4-module quiet zone.
    """
    matrix = [list(row) for row in qr.matrix_iter(scale=8, border=4)]
    height, width = len(matrix), len(matrix[0])
    img = Image.new("L", (width, height), 255)
    img.putdata([0 if dark else 255 for row in matrix for dark in row])
    return img


def compose_canvas() -> Image.Image:
    """Place every code from ``CODE_SPECS`` on one white canvas.

    Returns:
        The composed grayscale image.
    """
    canvas = Image.new("L", CANVAS_SIZE, 255)
    for spec, pos in zip(CODE_SPECS, POSITIONS):
        # No resizing here: resampling a rendered code makes module widths
        # uneven, which would test the generator rather than the decoders.
        canvas.paste(render_code(spec), pos)
    draw = ImageDraw.Draw(canvas)
    draw.text((60, 1040), "sample sheet: multiple codes in one image", fill=0)
    return canvas


def make_photo_like(img: Image.Image) -> Image.Image:
    """Degrade an image so it resembles a slightly tilted, blurry photo.

    Args:
        img: Clean source image.

    Returns:
        A rotated, blurred and noisy copy.
    """
    rnd = random.Random(RANDOM_SEED)
    out = img.rotate(7, expand=True, fillcolor=255)
    out = out.filter(ImageFilter.GaussianBlur(radius=1.5))
    pixels = out.load()
    # Sparse salt-and-pepper noise simulates sensor noise and dust.
    for _ in range(out.width * out.height // 200):
        x, y = rnd.randrange(out.width), rnd.randrange(out.height)
        pixels[x, y] = rnd.choice((0, 255))
    return out


def main() -> None:
    """Generate all sample images and the expected-results manifest.

    Returns:
        None
    """
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    clean = compose_canvas()
    expected_codes = [
        {"format": s["format"], "text": s["text"]} for s in CODE_SPECS
    ]

    images: dict[str, tuple[Image.Image, dict]] = {
        "01_clean.png": (clean, {}),
        "02_photo_like.jpg": (make_photo_like(clean), {"quality": 55}),
        # Half size makes modules ~2-3 px wide, close to the lower limit
        # seen when a whole sheet is photographed from a distance.
        "03_small.png": (
            clean.resize(
                (clean.width // 2, clean.height // 2), Image.BILINEAR
            ),
            {},
        ),
        "04_no_code.png": (Image.new("L", (800, 600), 230), {}),
    }
    manifest: dict[str, list[dict]] = {}
    for name, (img, save_opts) in images.items():
        img.save(SAMPLES_DIR / name, **save_opts)
        manifest[name] = [] if name == "04_no_code.png" else expected_codes

    (SAMPLES_DIR / "expected.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"generated {len(images)} images in {SAMPLES_DIR}")


if __name__ == "__main__":
    main()
