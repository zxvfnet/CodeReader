"""Compare pyzbar and zxing-cpp on the generated sample images.

Reads ``samples/expected.json`` written by ``generate_samples.py`` and prints,
per image and per decoder, how many expected codes were decoded correctly,
which were missed, and which results were unexpected (e.g. garbled text).

Usage:
    python scripts/generate_samples.py
    python scripts/compare_decoders.py
"""

import json
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import zxingcpp
from PIL import Image
from pyzbar import pyzbar

SAMPLES_DIR = Path(__file__).parent / "samples"

# pyzbar reports zbar symbol names; map them to zxing-cpp names so that both
# decoders are scored against the same expected format labels.
PYZBAR_FORMAT_MAP: dict[str, str] = {
    "QRCODE": "QRCode",
    "CODE128": "Code128",
    "EAN13": "EAN13",
    "CODE39": "Code39",
}

Decoded = tuple[str, str]  # (format, text)


def decode_with_pyzbar(img: Image.Image) -> list[Decoded]:
    """Decode every symbol in ``img`` with pyzbar.

    Args:
        img: Grayscale image.

    Returns:
        A list of (format, text) tuples.
    """
    results = []
    for obj in pyzbar.decode(img):
        # Same decoding as the existing qr_reader.py, so the comparison
        # shows how the current app would behave.
        text = obj.data.decode("utf-8", errors="replace")
        results.append((PYZBAR_FORMAT_MAP.get(obj.type, obj.type), text))
    return results


def decode_with_zxing(img: Image.Image) -> list[Decoded]:
    """Decode every symbol in ``img`` with zxing-cpp.

    Args:
        img: Grayscale image.

    Returns:
        A list of (format, text) tuples.
    """
    return [(b.format.name, b.text) for b in zxingcpp.read_barcodes(img)]


def decode_with_zxing_upscaled(img: Image.Image) -> list[Decoded]:
    """Decode with zxing-cpp on the original and on a 2x upscaled image.

    In early trials zxing-cpp missed thin 1D barcodes in small or blurry
    images; upscaling widens the bars enough for its binarizer. Running the
    original first keeps codes that only decode at native resolution.

    Args:
        img: Grayscale image.

    Returns:
        A list of unique (format, text) tuples, in first-found order.
    """
    upscaled = img.resize((img.width * 2, img.height * 2), Image.BICUBIC)
    found = decode_with_zxing(img) + decode_with_zxing(upscaled)
    # dict.fromkeys de-duplicates while keeping order. Identical codes printed
    # twice would collapse here; position-based de-duplication will handle
    # that in the real implementation.
    return list(dict.fromkeys(found))


def score(
    expected: list[Decoded], actual: list[Decoded]
) -> tuple[int, Counter, Counter]:
    """Match decoded results against the expected ones.

    Matching is done on (format, text) as a multiset so duplicates are counted
    correctly and a garbled text counts as both a miss and an unexpected item.

    Args:
        expected: Expected (format, text) tuples.
        actual: Decoded (format, text) tuples.

    Returns:
        A tuple of (correct count, missed items, unexpected items).
    """
    exp, act = Counter(expected), Counter(actual)
    hit = exp & act
    return sum(hit.values()), exp - hit, act - hit


def main() -> None:
    """Run both decoders on every sample image and print a report.

    Returns:
        None

    Raises:
        FileNotFoundError: If the samples have not been generated yet.
    """
    manifest = json.loads(
        (SAMPLES_DIR / "expected.json").read_text(encoding="utf-8")
    )
    decoders: dict[str, Callable[[Image.Image], list[Decoded]]] = {
        "pyzbar": decode_with_pyzbar,
        "zxing-cpp": decode_with_zxing,
        "zxing+2x": decode_with_zxing_upscaled,
    }
    totals = {name: [0, 0] for name in decoders}  # [correct, expected]

    for image_name, codes in manifest.items():
        expected = [(c["format"], c["text"]) for c in codes]
        with Image.open(SAMPLES_DIR / image_name) as src:
            img = src.convert("L")
        print(f"\n=== {image_name} (expected {len(expected)}) ===")
        for name, decode in decoders.items():
            start = time.perf_counter()
            actual = decode(img)
            elapsed_ms = (time.perf_counter() - start) * 1000
            correct, missed, unexpected = score(expected, actual)
            totals[name][0] += correct
            totals[name][1] += len(expected)
            print(
                f"  {name:<10} correct {correct}/{len(expected)}"
                f"  {elapsed_ms:7.1f} ms"
            )
            for fmt, text in missed.elements():
                print(f"    missed     : {fmt} {text!r}")
            for fmt, text in unexpected.elements():
                print(f"    unexpected : {fmt} {text!r}")

    print("\n=== total ===")
    for name, (correct, total) in totals.items():
        print(f"  {name:<10} {correct}/{total}")


if __name__ == "__main__":
    main()
