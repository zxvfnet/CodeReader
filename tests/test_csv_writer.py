"""Tests for code_reader.csv_writer."""

from pathlib import Path

import pytest

from code_reader.decoder import DecodedCode
from code_reader.files import FileResult
from code_reader.csv_writer import (
    HEADER,
    NOTE_NO_CODE,
    build_rows,
    format_position,
    to_excel_cell,
    to_csv_field,
    write_csv,
)

SQUARE = ((10, 20), (110, 20), (110, 70), (10, 70))


def _code(text: str, fmt: str = "QRCode", note: str = "") -> DecodedCode:
    """Build a DecodedCode at a fixed position.

    Args:
        text: Decoded text.
        fmt: Format name.
        note: Note text.

    Returns:
        The DecodedCode.
    """
    return DecodedCode(fmt, text, SQUARE, note)


# ── cell conversion ──────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "4901234567894",
            '="4901234567894"',
        ),  # long number would become 4.9E+12
        ("0012", '="0012"'),  # leading zeros would be lost
        ("=1+1", "'=1+1"),  # formula injection
        ("+81-3", "'+81-3"),
        ("-5", "'-5"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("https://example.com", "https://example.com"),
        ("日本語", "日本語"),
        ("", ""),
        ("1" * 255, '="' + "1" * 255 + '"'),  # formula string length limit
        ("1" * 256, "1" * 256),
    ],
)
def test_to_excel_cell(text: str, expected: str) -> None:
    """Values are protected from Excel's automatic conversion."""
    assert to_excel_cell(text) == expected


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("plain", "plain"),
        ('say "hi"', 'say "hi"'),  # inner quotes alone do not need quoting
        ('="0012"', '="0012"'),  # must stay unquoted for Excel
        ("a,b", '"a,b"'),
        ("a\tb", "a\tb"),  # tabs are ordinary characters in CSV
        ('a,"b"', '"a,""b"""'),
        ("line1\nline2", '"line1\nline2"'),
        ('"start', '"""start"'),
    ],
)
def test_to_csv_field(cell: str, expected: str) -> None:
    """Only cells that would break the layout are quoted."""
    assert to_csv_field(cell) == expected


def test_format_position() -> None:
    """Position is written as labelled numbers so Excel keeps it as text."""
    assert format_position(_code("x")) == "x=10 y=20 w=100 h=50"


# ── rows and file output ─────────────────────────────


def test_build_rows_includes_errors_and_empty_files() -> None:
    """Every file appears in the output, even without codes."""
    results = [
        FileResult(
            Path("a.png"), [_code("A"), _code("0012", "EAN13", "要確認")]
        ),
        FileResult(Path("empty.png")),
        FileResult(Path("bad.png"), error="画像を読み込めません"),
    ]
    assert build_rows(results) == [
        ["a.png", "QRCode", "A", "x=10 y=20 w=100 h=50", ""],
        ["a.png", "EAN13", '="0012"', "x=10 y=20 w=100 h=50", "要確認"],
        ["empty.png", "", "", "", NOTE_NO_CODE],
        ["bad.png", "", "", "", "画像を読み込めません"],
    ]


def test_write_csv_encoding_and_line_endings(tmp_path: Path) -> None:
    """File is UTF-8 with BOM and CRLF so Excel opens it without garbling."""
    out = tmp_path / "out.csv"
    count = write_csv(
        [FileResult(Path("画像.png"), [_code("日本語\n改行")])], out
    )

    raw = out.read_bytes()
    assert count == 1
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert (
        text
        == ",".join(HEADER)
        + "\r\n"
        + '画像.png,QRCode,"日本語\n改行",x=10 y=20 w=100 h=50,\r\n'
    )


def test_write_csv_with_no_results_writes_header_only(tmp_path: Path) -> None:
    """An empty batch still produces a valid file with a header."""
    out = tmp_path / "out.csv"
    assert write_csv([], out) == 0
    assert out.read_bytes().decode("utf-8-sig") == ",".join(HEADER) + "\r\n"


def test_write_csv_raises_when_folder_missing(tmp_path: Path) -> None:
    """Write failures surface as OSError for the GUI to report."""
    with pytest.raises(OSError):
        write_csv([], tmp_path / "missing" / "out.csv")


def test_build_rows_adds_file_warning_row() -> None:
    """A file-level warning gets its own row before the codes."""
    result = FileResult(Path("a.png"), [_code("A")], warning="上限")
    assert build_rows([result]) == [
        ["a.png", "", "", "", "上限"],
        ["a.png", "QRCode", "A", "x=10 y=20 w=100 h=50", ""],
    ]
