"""Tests for code_reader.decoder."""

import pytest
from PIL import Image

from code_reader import decoder
from code_reader.decoder import DecodedCode, decode_image
from tests.support.code_images import compose


def _pairs(codes: list[DecodedCode]) -> list[tuple[str, str]]:
    """Return (format, text) pairs for compact assertions.

    Args:
        codes: Decoded codes.

    Returns:
        List of (format, text).
    """
    return [(c.format, c.text) for c in codes]


# ── normal cases ─────────────────────────────────────


@pytest.mark.parametrize(
    ("fmt", "text"),
    [
        ("QRCode", "https://example.com/?a=1"),
        ("QRCode", "日本語テキスト：品番A-001"),
        ("DataMatrix", "DM-0001"),
        ("Code128", "LOT-2026"),
        ("EAN13", "4901234567894"),
        ("Code39", "ABC-123"),
    ],
)
def test_decode_single_code(fmt: str, text: str) -> None:
    """Each supported symbology is decoded with its exact content."""
    assert _pairs(decode_image(compose([(fmt, text, (50, 50))]))) == [
        (fmt, text)
    ]


def test_decode_multiple_codes_in_reading_order() -> None:
    """All codes in one image are returned in reading order."""
    img = compose(
        [
            ("Code128", "BOTTOM", (50, 450)),
            ("QRCode", "RIGHT", (600, 50)),
            ("QRCode", "LEFT", (50, 50)),
        ]
    )
    assert _pairs(decode_image(img)) == [
        ("QRCode", "LEFT"),
        ("QRCode", "RIGHT"),
        ("Code128", "BOTTOM"),
    ]


def test_position_is_in_original_coordinates() -> None:
    """Points from the upscaled pass must not leak 2x coordinates."""
    (code,) = decode_image(compose([("QRCode", "POS", (300, 200))]))
    left, top, width, height = code.bbox
    # The rendered image includes a quiet zone, so the symbol starts a bit
    # inside the paste position.
    assert 300 <= left < 360 and 200 <= top < 260
    assert 0 < width < 200 and 0 < height < 200


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "1"])
def test_accepts_any_image_mode(mode: str) -> None:
    """Color, alpha and 1-bit images are converted internally."""
    img = compose([("QRCode", "MODE", (50, 50))]).convert(mode)
    assert _pairs(decode_image(img)) == [("QRCode", "MODE")]


# ── abnormal / boundary cases ────────────────────────


def test_blank_image_returns_empty_list() -> None:
    """An image without codes yields no results instead of an error."""
    assert decode_image(Image.new("L", (400, 300), 255)) == []


def test_one_pixel_image_returns_empty_list() -> None:
    """The smallest possible image is handled without errors."""
    assert decode_image(Image.new("L", (1, 1), 0)) == []


def test_identical_codes_at_different_places_are_kept() -> None:
    """Same content printed twice must stay two rows, not be de-duplicated."""
    img = compose(
        [("QRCode", "SAME", (50, 50)), ("QRCode", "SAME", (600, 50))]
    )
    assert _pairs(decode_image(img)) == [
        ("QRCode", "SAME"),
        ("QRCode", "SAME"),
    ]


def test_conflicting_values_between_passes_are_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A different value at the same place is reported via the note."""
    square = ((10, 10), (60, 10), (60, 60), (10, 60))

    def fake_read(img: Image.Image, scale: int) -> list[DecodedCode]:
        text = "4901234567894" if scale == 1 else "0961243561294"
        return [DecodedCode("EAN13", text, square)]

    monkeypatch.setattr(decoder, "_read", fake_read)
    (code,) = decode_image(Image.new("L", (100, 100), 255))
    assert code.text == "4901234567894"
    assert "0961243561294" in code.note


def test_same_place_different_format_is_not_merged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Overlap alone does not merge codes of different symbologies."""
    square = ((10, 10), (60, 10), (60, 60), (10, 60))

    def fake_read(img: Image.Image, scale: int) -> list[DecodedCode]:
        fmt = "QRCode" if scale == 1 else "DataMatrix"
        return [DecodedCode(fmt, "X", square)]

    monkeypatch.setattr(decoder, "_read", fake_read)
    assert sorted(_pairs(decode_image(Image.new("L", (100, 100), 255)))) == [
        ("DataMatrix", "X"),
        ("QRCode", "X"),
    ]


def test_code_found_only_in_upscaled_pass_is_added(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A code missed at native size but found after upscaling is kept."""
    square = ((10, 10), (60, 10), (60, 60), (10, 60))

    def fake_read(img: Image.Image, scale: int) -> list[DecodedCode]:
        return [] if scale == 1 else [DecodedCode("Code39", "ABC-123", square)]

    monkeypatch.setattr(decoder, "_read", fake_read)
    assert _pairs(decode_image(Image.new("L", (100, 100), 255))) == [
        ("Code39", "ABC-123")
    ]
