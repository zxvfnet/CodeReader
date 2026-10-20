"""Helpers that render QR codes / barcodes into images for tests."""

from pathlib import Path

import zxingcpp
from PIL import Image

# Large enough for every helper layout used in the tests.
DEFAULT_CANVAS = (1200, 800)


def render_code(fmt: str, text: str, scale: int = 4) -> Image.Image:
    """Render one code as a grayscale image with a quiet zone.

    Args:
        fmt: zxing-cpp format name such as ``"QRCode"`` or ``"Code128"``.
        text: Content to encode.
        scale: Pixels per module.

    Returns:
        The rendered code in mode ``"L"``.
    """
    barcode = zxingcpp.create_barcode(
        text, getattr(zxingcpp.BarcodeFormat, fmt)
    )
    img = Image.fromarray(barcode.to_image(scale=scale)).convert("L")
    # 1D codes are rendered one module tall; give them a printable height.
    if img.height < 20:
        img = img.resize((img.width, 150), Image.NEAREST)
    return img


def compose(
    placements: list[tuple[str, str, tuple[int, int]]],
    size: tuple[int, int] = DEFAULT_CANVAS,
) -> Image.Image:
    """Place several codes on a white canvas.

    Args:
        placements: List of (format, text, (left, top)).
        size: Canvas size.

    Returns:
        The composed grayscale image.
    """
    canvas = Image.new("L", size, 255)
    for fmt, text, pos in placements:
        canvas.paste(render_code(fmt, text), pos)
    return canvas


def save_image(img: Image.Image, path: Path) -> Path:
    """Save an image, creating parent folders as needed.

    Args:
        img: Image to save.
        path: Destination path; the suffix decides the format.

    Returns:
        ``path`` for convenient chaining in tests.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path
