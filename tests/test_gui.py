"""Tests for code_reader.gui.

Pure helper functions are always tested. Tests that open a window are
skipped when no display is available (e.g. a headless CI machine).
"""

import datetime
import time
import tkinter as tk
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from tkinterdnd2 import TkinterDnD

from code_reader import gui
from code_reader.decoder import DecodedCode
from code_reader.files import FileResult
from code_reader.gui import (
    STATUS_ERROR,
    STATUS_NONE,
    STATUS_OK,
    STATUS_WARN,
    CodeReaderApp,
    default_csv_name,
    file_status,
    fit_ratio,
    is_image_file,
    summarize,
)
from tests.support.code_images import compose, save_image

SQUARE = ((0, 0), (10, 0), (10, 10), (0, 10))
WAIT_SECONDS = 20


def _result(
    name: str, notes: list[str] | None = None, error: str = ""
) -> FileResult:
    """Build a FileResult with one code per note.

    Args:
        name: File name.
        notes: Note for each code; None or [] gives no codes.
        error: Error message.

    Returns:
        The FileResult.
    """
    codes = [DecodedCode("QRCode", "X", SQUARE, n) for n in notes or []]
    return FileResult(Path(name), codes, error)


# ── pure helpers ─────────────────────────────────────


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (_result("a.png", [""]), STATUS_OK),
        (_result("a.png", ["", "要確認"]), STATUS_WARN),
        (_result("a.png"), STATUS_NONE),
        (_result("a.png", error="壊れています"), STATUS_ERROR),
        (
            FileResult(
                Path("a.png"), _result("a.png", [""]).codes, "", "上限"
            ),
            STATUS_WARN,
        ),
    ],
)
def test_file_status(result: FileResult, expected: str) -> None:
    """Each kind of result gets the matching status label."""
    assert file_status(result) == expected


def test_summarize_counts_warnings_and_errors() -> None:
    """The summary mentions only the problems that exist."""
    ok = [_result("a.png", ["", ""]), _result("b.png")]
    assert summarize(ok) == "2 枚の画像から 2 件のコードを読み取りました"
    mixed = ok + [_result("c.png", ["要確認"]), _result("d.png", error="x")]
    assert summarize(mixed).endswith("要確認 1 枚　／　読めない画像 1 枚")


def test_summarize_empty() -> None:
    """No results gives a zero summary rather than an error."""
    assert summarize([]) == "0 枚の画像から 0 件のコードを読み取りました"


def test_default_csv_name() -> None:
    """The default name contains a sortable timestamp."""
    now = datetime.datetime(2026, 10, 18, 9, 5, 7)
    assert default_csv_name(now) == "読み取り結果_20261018_090507.csv"


@pytest.mark.parametrize(
    ("src", "dst", "expected"),
    [
        ((1000, 500), (500, 500), 0.5),  # limited by width
        ((500, 1000), (500, 500), 0.5),  # limited by height
        ((100, 100), (500, 500), 1.0),  # never enlarged
        ((100, 100), (0, 0), 1.0),  # canvas not yet laid out
    ],
)
def test_fit_ratio(
    src: tuple[int, int], dst: tuple[int, int], expected: float
) -> None:
    """Images shrink to fit but are never enlarged."""
    assert fit_ratio(src, dst) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [("a.PNG", True), ("b.jpeg", True), ("c.pdf", False), ("noext", False)],
)
def test_is_image_file(name: str, expected: bool) -> None:
    """Suffix check is case-insensitive."""
    assert is_image_file(Path(name)) is expected


# ── window tests ─────────────────────────────────────


@pytest.fixture
def app() -> Iterator[CodeReaderApp]:
    """Create the main window, or skip when there is no display."""
    try:
        root = TkinterDnD.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no display: {exc}")
    root.withdraw()
    yield CodeReaderApp(root)
    root.destroy()


def _wait_idle(app: CodeReaderApp) -> None:
    """Pump Tk events until the background decoding has finished.

    Args:
        app: Application under test.

    Raises:
        AssertionError: If decoding does not finish in time.
    """
    deadline = time.monotonic() + WAIT_SECONDS
    while app._busy:
        assert time.monotonic() < deadline, "decoding did not finish"
        app.root.update()
        time.sleep(0.02)
    # Selection events raised by the last result are queued; process them.
    app.root.update()


@pytest.fixture
def images(tmp_path: Path) -> list[Path]:
    """Create one image with two codes and one image without codes."""
    two = compose([("QRCode", "ONE", (50, 50)), ("Code128", "TWO", (50, 450))])
    return [
        save_image(two, tmp_path / "with codes.png"),
        save_image(compose([], size=(200, 200)), tmp_path / "empty.png"),
    ]


def test_add_paths_decodes_and_lists_files(
    app: CodeReaderApp, images: list[Path]
) -> None:
    """Added images are decoded and shown with count and status."""
    app.add_paths(images)
    _wait_idle(app)

    rows = {
        iid: app.file_tree.item(iid, "values")
        for iid in app.file_tree.get_children()
    }
    assert rows[str(images[0])][1:] == ("2", STATUS_OK)
    assert rows[str(images[1])][1:] == ("0", STATUS_NONE)
    assert str(app.btn_save["state"]) == tk.NORMAL
    # Selecting a file lists its codes in the lower table.
    app.file_tree.selection_set(str(images[0]))
    app.root.update()
    texts = [
        app.code_tree.item(i, "values")[2]
        for i in app.code_tree.get_children()
    ]
    assert texts == ["ONE", "TWO"]


def test_adding_same_file_twice_is_ignored(
    app: CodeReaderApp, images: list[Path]
) -> None:
    """Duplicates are not listed again."""
    app.add_paths(images[:1])
    _wait_idle(app)
    app.add_paths(images[:1])
    assert len(app.file_tree.get_children()) == 1
    assert "新しい画像がありません" in app.status_var.get()


def test_drop_accepts_paths_with_spaces_and_skips_non_images(
    app: CodeReaderApp, images: list[Path], tmp_path: Path
) -> None:
    """Tcl-quoted dropped paths are parsed; non-images are skipped."""
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF")
    data = f"{{{images[0]}}} {pdf}"
    app._on_drop(SimpleNamespace(data=data))
    _wait_idle(app)
    assert app.file_tree.get_children() == (str(images[0]),)


def test_save_writes_csv(
    app: CodeReaderApp,
    images: list[Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving writes all files' rows to the chosen path."""
    out = tmp_path / "out.csv"
    monkeypatch.setattr(
        gui.filedialog, "asksaveasfilename", lambda **kw: str(out)
    )
    app.add_paths(images)
    _wait_idle(app)
    app._on_save()
    lines = out.read_bytes().decode("utf-8-sig").splitlines()
    assert len(lines) == 1 + 3  # header + 2 codes + 1 "no code" row


def test_save_reports_write_error(
    app: CodeReaderApp,
    images: list[Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A write failure is shown to the user instead of crashing."""
    shown: list[str] = []
    monkeypatch.setattr(
        gui.filedialog,
        "asksaveasfilename",
        lambda **kw: str(tmp_path / "missing" / "out.csv"),
    )
    monkeypatch.setattr(
        gui.messagebox, "showerror", lambda title, msg: shown.append(msg)
    )
    app.add_paths(images[:1])
    _wait_idle(app)
    app._on_save()
    assert shown and "保存できませんでした" in shown[0]


def test_save_without_results_shows_message(
    app: CodeReaderApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Saving an empty list tells the user instead of writing a file."""
    shown: list[str] = []
    monkeypatch.setattr(
        gui.messagebox, "showinfo", lambda title, msg: shown.append(msg)
    )
    app._on_save()
    assert shown == ["保存する読み取り結果がありません。"]


def test_remove_and_clear(app: CodeReaderApp, images: list[Path]) -> None:
    """Delete removes one file; removing the last one resets the view."""
    app.add_paths(images)
    _wait_idle(app)
    app.file_tree.selection_set(str(images[1]))
    app._on_remove_selected()
    assert app.file_tree.get_children() == (str(images[0]),)

    app.file_tree.selection_set(str(images[0]))
    app._on_remove_selected()
    assert app.file_tree.get_children() == ()
    assert str(app.btn_save["state"]) == tk.DISABLED


def test_copy_selected_code(app: CodeReaderApp, images: list[Path]) -> None:
    """Double-click copies the selected code's text to the clipboard."""
    app.add_paths(images[:1])
    _wait_idle(app)
    app.code_tree.selection_set("1")
    app._on_copy_code()
    assert app.root.clipboard_get() == "TWO"
