"""Decode every 2D code and barcode contained in one image.

zxing-cpp is run twice: on the original image and on a 2x upscaled copy.
The step 1 trial (see docs/developer.md) showed that thin 1D barcodes in
small or blurry images are often missed at native resolution but recovered
after upscaling. Results of both passes are merged by position.
"""

from dataclasses import dataclass

import zxingcpp
from PIL import Image

UPSCALE_FACTOR = 2
# zxing-cpp's Python read_barcodes() stops after this many symbols per call
# and does not expose the setting (max_number_of_symbols = 0xff in
# wrappers/python/zxing.cpp, v3.1.1). Callers use it to warn about misses.
MAX_SYMBOLS_PER_PASS = 255
NOTE_CONFLICT = "要確認：拡大読み取りで別の値（{other}）"

Point = tuple[int, int]


@dataclass
class DecodedCode:
    """One decoded code.

    Attributes:
        format: Symbology name such as ``"QRCode"`` or ``"EAN13"``.
        text: Decoded content.
        points: Corner points (top-left, top-right, bottom-right, bottom-left)
            in original image coordinates.
        note: Remark for the user, e.g. a warning that the value is uncertain.
    """

    format: str
    text: str
    points: tuple[Point, Point, Point, Point]
    note: str = ""

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """Return the axis-aligned bounding box.

        Returns:
            A tuple of (left, top, width, height).
        """
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)

    @property
    def center(self) -> tuple[float, float]:
        """Return the center of the bounding box.

        Returns:
            A tuple of (x, y).
        """
        left, top, width, height = self.bbox
        return left + width / 2, top + height / 2

    def contains(self, x: float, y: float) -> bool:
        """Check whether a point lies inside the bounding box.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            True if the point is inside or on the edge of the box.
        """
        left, top, width, height = self.bbox
        return left <= x <= left + width and top <= y <= top + height


def _read(img: Image.Image, scale: int) -> list[DecodedCode]:
    """Run zxing-cpp once and convert results to original coordinates.

    Args:
        img: Image to decode (already scaled by ``scale``).
        scale: Factor by which ``img`` is larger than the original image.

    Returns:
        Decoded codes with points divided by ``scale``.
    """
    codes = []
    for barcode in zxingcpp.read_barcodes(img):
        pos = barcode.position
        corners = (
            pos.top_left,
            pos.top_right,
            pos.bottom_right,
            pos.bottom_left,
        )
        points = tuple((p.x // scale, p.y // scale) for p in corners)
        codes.append(DecodedCode(barcode.format.name, barcode.text, points))
    return codes


def _find_same_location(
    code: DecodedCode, candidates: list[DecodedCode]
) -> DecodedCode | None:
    """Find a code of the same format at the same location.

    Two results are treated as the same physical code when the center of one
    lies inside the other's bounding box. This tolerates the small coordinate
    shifts caused by upscaling, while keeping identical codes printed at
    different places as separate rows.

    Args:
        code: Code to look up.
        candidates: Codes already found.

    Returns:
        The matching candidate, or None.
    """
    cx, cy = code.center
    for other in candidates:
        if other.format != code.format:
            continue
        ox, oy = other.center
        if other.contains(cx, cy) or code.contains(ox, oy):
            return other
    return None


def decode_image(img: Image.Image) -> list[DecodedCode]:
    """Decode all codes in an image.

    Args:
        img: Source image in any PIL mode.

    Returns:
        Decoded codes sorted top-to-bottom, then left-to-right. A code whose
        value differs between the two passes keeps the native-resolution
        value and gets a note, because one of the values must be a misread
        and only the user can tell which.
    """
    gray = img.convert("L")
    results = _read(gray, 1)

    upscaled = gray.resize(
        (gray.width * UPSCALE_FACTOR, gray.height * UPSCALE_FACTOR),
        Image.BICUBIC,
    )
    for code in _read(upscaled, UPSCALE_FACTOR):
        same = _find_same_location(code, results)
        if same is None:
            results.append(code)
        elif same.text != code.text and not same.note:
            same.note = NOTE_CONFLICT.format(other=code.text)

    # Reading order makes the CSV rows match how a person scans the sheet.
    results.sort(key=lambda c: (c.bbox[1], c.bbox[0]))
    return results
