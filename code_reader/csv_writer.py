"""Write decode results as a CSV file that opens cleanly in Excel."""

import re
from collections.abc import Iterable
from pathlib import Path

from code_reader.decoder import DecodedCode
from code_reader.files import FileResult

HEADER = ["ファイル名", "種別", "読み取り内容", "位置", "備考"]
NOTE_NO_CODE = "コードが見つかりません"

# Excel turns digit-only strings into numbers, dropping leading zeros and
# showing long ones like EAN13 as 4.90123E+12.
_DIGITS_ONLY = re.compile(r"\d+")
# Cells starting with these are evaluated as formulas by Excel
# (CSV injection), and QR content is untrusted input.
_FORMULA_PREFIXES = ("=", "+", "-", "@")
# Excel rejects string literals longer than this inside a formula.
_EXCEL_FORMULA_STRING_LIMIT = 255
DELIMITER = ","
# Only these characters break the CSV structure, so only cells containing
# them are quoted. The csv module would also quote the ="..." cells (they
# contain quotes), and Excel was confirmed to evaluate that trick when it is
# unquoted.
_NEEDS_QUOTING = (DELIMITER, "\r", "\n")


def to_excel_cell(text: str) -> str:
    """Protect a value so Excel shows it exactly as decoded.

    Args:
        text: Raw decoded text.

    Returns:
        ``="..."`` for digit-only strings (keeps them as text), a leading
        apostrophe for formula-like strings, otherwise ``text`` unchanged.
    """
    if (
        _DIGITS_ONLY.fullmatch(text)
        and len(text) <= _EXCEL_FORMULA_STRING_LIMIT
    ):
        return f'="{text}"'
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def to_csv_field(cell: str) -> str:
    """Quote a cell only when it would otherwise break the CSV layout.

    Args:
        cell: Cell value.

    Returns:
        The cell wrapped in double quotes (inner quotes doubled) if it
        contains a comma or line break or starts with a quote, else unchanged.
    """
    if cell.startswith('"') or any(ch in cell for ch in _NEEDS_QUOTING):
        return '"' + cell.replace('"', '""') + '"'
    return cell


def format_position(code: DecodedCode) -> str:
    """Format the bounding box in a way Excel will not parse as a number.

    Args:
        code: Decoded code.

    Returns:
        A string such as ``"x=92 y=92 w=232 h=232"``.
    """
    left, top, width, height = code.bbox
    return f"x={left} y={top} w={width} h={height}"


def build_rows(results: Iterable[FileResult]) -> list[list[str]]:
    """Convert decode results to CSV rows (without header).

    Files with no codes or with errors still get one row, so the user can see
    in Excel which images need attention instead of them silently vanishing.

    Args:
        results: Per-file decode results.

    Returns:
        Rows of cell strings.
    """
    rows = []
    for result in results:
        name = result.path.name
        if result.error:
            rows.append([name, "", "", "", result.error])
        elif not result.codes:
            rows.append([name, "", "", "", NOTE_NO_CODE])
        if result.warning:
            rows.append([name, "", "", "", result.warning])
        for code in result.codes:
            rows.append(
                [
                    name,
                    code.format,
                    to_excel_cell(code.text),
                    format_position(code),
                    code.note,
                ]
            )
    return rows


def write_csv(results: Iterable[FileResult], path: Path) -> int:
    """Write results to a CSV file.

    The file is UTF-8 with BOM: without the BOM, Excel opens a double-clicked
    file as Shift_JIS and Japanese text is garbled.

    Args:
        results: Per-file decode results.
        path: Output file path.

    Returns:
        Number of data rows written (excluding header).

    Raises:
        OSError: If the file cannot be written (e.g. it is open in Excel).
    """
    rows = build_rows(results)
    # newline="" keeps Python from translating line endings, so the file has
    # CRLF on every OS, which is what Excel writes and expects.
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        for row in [HEADER, *rows]:
            line = DELIMITER.join(to_csv_field(cell) for cell in row)
            f.write(line + "\r\n")
    return len(rows)
