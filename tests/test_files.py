"""Tests for code_reader.files."""

from pathlib import Path

import pytest
from PIL import Image

from code_reader import files
from code_reader.decoder import MAX_SYMBOLS_PER_PASS, DecodedCode
from code_reader.files import (
    NOTE_LIMIT,
    collect_image_paths,
    load_image,
    read_files,
)
from tests.support.code_images import compose, render_code, save_image


@pytest.fixture
def qr_image() -> Image.Image:
    """Return an image containing one QR code."""
    return compose([("QRCode", "FILE", (50, 50))], size=(400, 400))


# ── collect_image_paths ──────────────────────────────


def test_collect_expands_folder_one_level(
    tmp_path: Path, qr_image: Image.Image
) -> None:
    """Only image files directly inside the folder are collected."""
    a = save_image(qr_image, tmp_path / "b.png")
    b = save_image(qr_image, tmp_path / "a.JPG")
    save_image(qr_image, tmp_path / "sub" / "nested.png")
    (tmp_path / "memo.txt").write_text("x", encoding="utf-8")
    assert collect_image_paths([tmp_path]) == sorted([a, b])


def test_collect_keeps_explicit_file_and_removes_duplicates(
    tmp_path: Path, qr_image: Image.Image
) -> None:
    """Explicit files are kept even if unknown; duplicates collapse."""
    img = save_image(qr_image, tmp_path / "a.png")
    other = tmp_path / "data.bin"
    other.write_bytes(b"x")
    assert collect_image_paths([img, tmp_path, other]) == sorted([img, other])


def test_collect_ignores_missing_paths_and_empty_input(tmp_path: Path) -> None:
    """Non-existent paths and an empty selection give an empty list."""
    assert collect_image_paths([tmp_path / "missing.png"]) == []
    assert collect_image_paths([]) == []


# ── load_image / read_files ──────────────────────────


def test_load_image_with_japanese_path(
    tmp_path: Path, qr_image: Image.Image
) -> None:
    """Non-ASCII paths, common on Japanese Windows, can be read."""
    path = save_image(qr_image, tmp_path / "日本語フォルダ" / "画像.png")
    assert load_image(path).size == qr_image.size


def test_read_files_continues_after_broken_file(
    tmp_path: Path, qr_image: Image.Image
) -> None:
    """A broken file is reported and does not stop the batch."""
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")
    good = save_image(qr_image, tmp_path / "good.png")

    results = read_files([broken, good, tmp_path / "missing.png"])

    assert [r.path for r in results] == [
        broken,
        good,
        tmp_path / "missing.png",
    ]
    assert results[0].error and not results[0].codes
    assert [c.text for c in results[1].codes] == ["FILE"] and results[
        1
    ].error == ""
    assert results[2].error


def test_read_files_reports_progress(
    tmp_path: Path, qr_image: Image.Image
) -> None:
    """The progress callback receives (index, total, path) for each file."""
    paths = [save_image(qr_image, tmp_path / f"{i}.png") for i in range(3)]
    calls: list[tuple[int, int, Path]] = []
    read_files(paths, on_progress=lambda i, n, p: calls.append((i, n, p)))
    assert calls == [(1, 3, paths[0]), (2, 3, paths[1]), (3, 3, paths[2])]


def test_read_files_with_no_paths() -> None:
    """An empty batch returns an empty list."""
    assert read_files([]) == []


# ── detection limit ──────────────────────────────────


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (MAX_SYMBOLS_PER_PASS - 1, ""),
        (MAX_SYMBOLS_PER_PASS, NOTE_LIMIT),
        (MAX_SYMBOLS_PER_PASS + 1, NOTE_LIMIT),
    ],
)
def test_limit_warning_boundary(
    tmp_path: Path,
    qr_image: Image.Image,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    expected: str,
) -> None:
    """A warning is set exactly when the per-pass cap is reached."""
    square = ((0, 0), (1, 0), (1, 1), (0, 1))
    fake = [DecodedCode("QRCode", str(i), square) for i in range(count)]
    monkeypatch.setattr(files, "decode_image", lambda img: fake)
    (result,) = read_files([save_image(qr_image, tmp_path / "a.png")])
    assert result.warning == expected


def test_limit_warning_with_real_image(tmp_path: Path) -> None:
    """An image with more codes than the cap is decoded up to the cap."""
    tile = render_code("QRCode", "Q000")
    cols, total = 20, MAX_SYMBOLS_PER_PASS + 20
    rows = -(-total // cols)
    canvas = Image.new("L", (cols * tile.width, rows * tile.height), 255)
    for i in range(total):
        pos = ((i % cols) * tile.width, (i // cols) * tile.height)
        canvas.paste(render_code("QRCode", f"Q{i:03d}"), pos)

    (result,) = read_files([save_image(canvas, tmp_path / "many.png")])

    assert len(result.codes) == MAX_SYMBOLS_PER_PASS
    assert result.warning == NOTE_LIMIT
