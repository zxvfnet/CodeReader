"""Tests for the command-line entry point (python -m code_reader)."""

from pathlib import Path

import pytest

from code_reader.__main__ import main
from tests.support.code_images import compose, save_image


def test_cli_writes_csv_for_folder(tmp_path: Path) -> None:
    """A folder argument is expanded and all codes go into the CSV."""
    img = compose([("QRCode", "ONE", (50, 50)), ("Code128", "TWO", (50, 450))])
    save_image(img, tmp_path / "in" / "sheet.png")
    out = tmp_path / "result.csv"

    assert main([str(tmp_path / "in"), "-o", str(out)]) == 0

    lines = out.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 3
    assert lines[1].split(",")[1:3] == ["QRCode", "ONE"]
    assert lines[2].split(",")[1:3] == ["Code128", "TWO"]


def test_cli_returns_error_when_no_images(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty folder gives exit code 1 and writes no file."""
    out = tmp_path / "result.csv"
    assert main([str(tmp_path), "-o", str(out)]) == 1
    assert not out.exists()
    assert "見つかりません" in capsys.readouterr().err
