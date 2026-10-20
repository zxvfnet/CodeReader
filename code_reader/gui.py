"""Desktop GUI for reading QR codes and barcodes from images.

Layout:
    toolbar  : add images / add folder / clear / save CSV
    left     : list of image files with code count and status
    right    : preview with code outlines (top) and decoded codes (bottom)
    bottom   : status message and progress bar

Decoding runs in a worker thread so the window stays responsive with large
batches. Tk is not thread-safe, so the worker only posts results to a queue
and the main thread polls it with ``after``.

Usage:
    python -m code_reader.gui
"""

import datetime
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font, messagebox

import ttkbootstrap as tb
from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

from code_reader.decoder import DecodedCode
from code_reader.files import (
    IMAGE_SUFFIXES,
    FileResult,
    collect_image_paths,
    load_image,
    read_files,
)
from code_reader.csv_writer import write_csv

APP_TITLE = "QR・バーコード読み取り"
THEME = "bootstrap-light"
# Fonts tried in order; the first installed one becomes the UI font.
FONT_CANDIDATES = ("Yu Gothic UI", "Meiryo UI", "Noto Sans CJK JP")
FONT_SIZE = 10
POLL_MS = 50
PREVIEW_BG = "#2b2b2b"
BOX_COLOR = "#2ecc71"
BOX_SELECTED_COLOR = "#ff7f0e"
DROP_HINT = "ここに画像やフォルダを\nドラッグ＆ドロップ\n\n（または上のボタンから追加）"

STATUS_WAITING = "待機中"
STATUS_OK = "✓ 完了"
STATUS_NONE = "－ なし"
STATUS_WARN = "⚠ 要確認"
STATUS_ERROR = "✕ エラー"


def file_status(result: FileResult) -> str:
    """Return the status label shown in the file list.

    Args:
        result: Decode result of one file.

    Returns:
        One of the ``STATUS_*`` labels.
    """
    if result.error:
        return STATUS_ERROR
    if not result.codes:
        return STATUS_NONE
    if result.warning or any(code.note for code in result.codes):
        return STATUS_WARN
    return STATUS_OK


def summarize(results: list[FileResult]) -> str:
    """Build the status bar message for finished results.

    Args:
        results: Results of all processed files.

    Returns:
        A one-line summary in Japanese.
    """
    codes = sum(len(r.codes) for r in results)
    errors = sum(1 for r in results if r.error)
    warns = sum(1 for r in results if file_status(r) == STATUS_WARN)
    text = f"{len(results)} 枚の画像から {codes} 件のコードを読み取りました"
    if warns:
        text += f"　／　要確認 {warns} 枚"
    if errors:
        text += f"　／　読めない画像 {errors} 枚"
    return text


def default_csv_name(now: datetime.datetime) -> str:
    """Return a default output file name that does not overwrite old ones.

    Args:
        now: Current time.

    Returns:
        A file name such as ``"読み取り結果_20261018_131500.csv"``.
    """
    return f"読み取り結果_{now:%Y%m%d_%H%M%S}.csv"


def fit_ratio(src: tuple[int, int], dst: tuple[int, int]) -> float:
    """Return the scale that fits ``src`` inside ``dst`` without enlarging.

    Args:
        src: Source (width, height).
        dst: Available (width, height).

    Returns:
        A ratio in (0, 1]; small images are shown at 100% so codes stay
        crisp rather than blurred by upscaling.
    """
    if min(src) <= 0 or min(dst) <= 0:
        return 1.0
    return min(dst[0] / src[0], dst[1] / src[1], 1.0)


def is_image_file(path: Path) -> bool:
    """Check whether a path looks like an image the app can read.

    Args:
        path: File path.

    Returns:
        True if the suffix is a supported image type.
    """
    return path.suffix.lower() in IMAGE_SUFFIXES


class CodeReaderApp:
    """Main window controller.

    Attributes:
        root: The Tk root window (TkinterDnD-enabled).
    """

    def __init__(self, root: TkinterDnD.Tk) -> None:
        """Build the window.

        Args:
            root: Tk root created with ``TkinterDnD.Tk()``.
        """
        self.root = root
        self._results: dict[Path, FileResult] = {}
        self._order: list[Path] = []
        self._queue: queue.Queue = queue.Queue()
        self._busy = False
        self._preview_img: Image.Image | None = None
        self._preview_path: Path | None = None
        self._photo: ImageTk.PhotoImage | None = None

        self._setup_style()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._register_drop()
        self._update_buttons()

    # ── construction ─────────────────────────────────

    def _setup_style(self) -> None:
        """Apply theme, Japanese UI font and window geometry.

        Returns:
            None
        """
        self.root.title(APP_TITLE)
        self.root.geometry("1200x760")
        self.root.minsize(900, 560)
        self.style = tb.Style(theme=THEME)

        families = set(font.families(self.root))
        family = next((f for f in FONT_CANDIDATES if f in families), None)
        for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont"):
            f = font.nametofont(name)
            f.configure(size=FONT_SIZE)
            if family:
                f.configure(family=family)
        # Taller rows make the tables easier to read and click.
        self.style.configure("Treeview", rowheight=28)

    def _build_toolbar(self) -> None:
        """Create the action buttons at the top.

        Returns:
            None
        """
        bar = tb.Frame(self.root, padding=(12, 10))
        bar.pack(side=tk.TOP, fill=tk.X)

        self.btn_add = tb.Button(
            bar,
            text="📂 画像を追加",
            bootstyle="primary",
            command=self._on_add_files,
            width=14,
        )
        self.btn_folder = tb.Button(
            bar,
            text="📁 フォルダを追加",
            bootstyle="primary-outline",
            command=self._on_add_folder,
            width=16,
        )
        self.btn_clear = tb.Button(
            bar,
            text="🗑 クリア",
            bootstyle="danger-outline",
            command=self._on_clear,
            width=10,
        )
        self.btn_save = tb.Button(
            bar,
            text="💾 CSVに保存",
            bootstyle="success",
            command=self._on_save,
            width=14,
        )
        self.btn_add.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_folder.pack(side=tk.LEFT, padx=6)
        self.btn_clear.pack(side=tk.LEFT, padx=6)
        self.btn_save.pack(side=tk.RIGHT)

    def _build_body(self) -> None:
        """Create the file list, preview and code table.

        Returns:
            None
        """
        paned = tb.Panedwindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))

        # Left: image file list.
        left = tb.Labelframe(paned, text=" 画像ファイル ", padding=6)
        self.file_tree = self._make_tree(
            left,
            [
                ("name", "ファイル名", 190, True),
                ("count", "件数", 50, False),
                ("status", "状態", 80, False),
            ],
        )
        self.file_tree.tag_configure("error", foreground="#c0392b")
        self.file_tree.tag_configure("warn", background="#fff3cd")
        self.file_tree.bind("<<TreeviewSelect>>", self._on_file_select)
        self.file_tree.bind("<Delete>", self._on_remove_selected)
        # The hint sits on top of the empty list so first-time users see
        # where to drop files; it is hidden once files are added.
        self.drop_hint = tb.Label(
            left,
            text=DROP_HINT,
            justify=tk.CENTER,
            anchor=tk.CENTER,
            bootstyle="secondary",
        )
        paned.add(left, weight=1)

        # Right: preview over code table.
        right = tb.Panedwindow(paned, orient=tk.VERTICAL)
        preview_frame = tb.Labelframe(right, text=" プレビュー ", padding=6)
        self.canvas = tk.Canvas(
            preview_frame, bg=PREVIEW_BG, highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self._draw_preview())
        right.add(preview_frame, weight=3)

        codes_frame = tb.Labelframe(
            right, text=" 読み取り結果（ダブルクリックでコピー） ", padding=6
        )
        self.code_tree = self._make_tree(
            codes_frame,
            [
                ("no", "No", 40, False),
                ("format", "種別", 100, False),
                ("text", "読み取り内容", 420, True),
                ("note", "備考", 260, True),
            ],
        )
        self.code_tree.tag_configure("warn", background="#fff3cd")
        self.code_tree.bind(
            "<<TreeviewSelect>>", lambda e: self._draw_preview()
        )
        self.code_tree.bind("<Double-1>", self._on_copy_code)
        right.add(codes_frame, weight=2)
        paned.add(right, weight=3)

        self._show_drop_hint(True)

    def _make_tree(
        self, parent: tk.Widget, columns: list[tuple[str, str, int, bool]]
    ) -> tb.Treeview:
        """Create a Treeview with a vertical scrollbar.

        Args:
            parent: Parent widget.
            columns: (id, heading, width, stretch) for each column.

        Returns:
            The created Treeview.
        """
        tree = tb.Treeview(
            parent,
            columns=[c[0] for c in columns],
            show="headings",
            selectmode="browse",
        )
        for col_id, heading, width, stretch in columns:
            tree.heading(col_id, text=heading, anchor=tk.W)
            tree.column(col_id, width=width, stretch=stretch, anchor=tk.W)
        scroll = tb.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return tree

    def _build_statusbar(self) -> None:
        """Create the status message and progress bar at the bottom.

        Returns:
            None
        """
        bar = tb.Frame(self.root, padding=(12, 4, 12, 10))
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var = tk.StringVar(
            value="画像をドラッグ＆ドロップするか、「画像を追加」を押してください"
        )
        tb.Label(bar, textvariable=self.status_var).pack(side=tk.LEFT)
        self.progress = tb.Progressbar(
            bar, length=240, mode="determinate", bootstyle="success-striped"
        )
        self.progress.pack(side=tk.RIGHT)

    def _register_drop(self) -> None:
        """Accept files and folders dropped anywhere on the window.

        Returns:
            None
        """
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self._on_drop)

    # ── user actions ─────────────────────────────────

    def _on_add_files(self) -> None:
        """Let the user pick one or more image files.

        Returns:
            None
        """
        patterns = " ".join(f"*{s}" for s in sorted(IMAGE_SUFFIXES))
        names = filedialog.askopenfilenames(
            title="画像ファイルを選択（複数可）",
            filetypes=[
                ("画像ファイル", patterns),
                ("すべてのファイル", "*.*"),
            ],
        )
        self.add_paths([Path(n) for n in names])

    def _on_add_folder(self) -> None:
        """Let the user pick a folder of images.

        Returns:
            None
        """
        folder = filedialog.askdirectory(title="画像フォルダを選択")
        if folder:
            self.add_paths([Path(folder)])

    def _on_drop(self, event: tk.Event) -> None:
        """Handle files/folders dropped onto the window.

        Args:
            event: Drop event; ``event.data`` is a Tcl list of paths
                (paths with spaces are wrapped in braces).

        Returns:
            None
        """
        dropped = [Path(p) for p in self.root.tk.splitlist(event.data)]
        # Silently skip non-image files dropped by mistake (e.g. a PDF next
        # to the images) instead of listing them as errors.
        self.add_paths([p for p in dropped if p.is_dir() or is_image_file(p)])

    def _on_clear(self) -> None:
        """Remove all files and results.

        Returns:
            None
        """
        self._results.clear()
        self._order.clear()
        self.file_tree.delete(*self.file_tree.get_children())
        self.code_tree.delete(*self.code_tree.get_children())
        self._preview_img = None
        self._preview_path = None
        self.canvas.delete("all")
        self.progress.configure(value=0)
        self._show_drop_hint(True)
        self._set_status("クリアしました")
        self._update_buttons()

    def _on_remove_selected(self, event: tk.Event | None = None) -> None:
        """Remove the selected file from the list (Delete key).

        Args:
            event: Key event (unused).

        Returns:
            None
        """
        if self._busy:
            return
        for iid in self.file_tree.selection():
            path = Path(iid)
            self._order.remove(path)
            self._results.pop(path, None)
            self.file_tree.delete(iid)
        if not self._order:
            self._on_clear()

    def _on_save(self) -> None:
        """Save all results to a CSV file chosen by the user.

        Returns:
            None
        """
        results = [self._results[p] for p in self._order if p in self._results]
        if not results:
            messagebox.showinfo(
                APP_TITLE, "保存する読み取り結果がありません。"
            )
            return
        out = filedialog.asksaveasfilename(
            title="CSVファイルの保存先",
            initialdir=str(self._order[0].parent),
            initialfile=default_csv_name(datetime.datetime.now()),
            defaultextension=".csv",
            filetypes=[("CSVファイル", "*.csv"), ("すべてのファイル", "*.*")],
        )
        if not out:
            return
        try:
            rows = write_csv(results, Path(out))
        except OSError as exc:
            # The most common cause is the same file being open in Excel.
            messagebox.showerror(
                APP_TITLE,
                f"保存できませんでした。\nExcel で開いていないか確認してください。\n\n{exc}",
            )
            return
        self._set_status(f"{rows} 行を保存しました: {out}")
        if sys.platform == "win32" and messagebox.askyesno(
            APP_TITLE, f"{rows} 行を保存しました。\nファイルを開きますか？"
        ):
            os.startfile(out)

    def _on_file_select(self, event: tk.Event | None = None) -> None:
        """Show the selected image and its codes.

        Args:
            event: Selection event (unused).

        Returns:
            None
        """
        selection = self.file_tree.selection()
        if not selection:
            return
        path = Path(selection[0])
        result = self._results.get(path)
        self._fill_code_table(result)
        try:
            self._preview_img = load_image(path)
            self._preview_path = path
        except (OSError, Image.DecompressionBombError):
            self._preview_img = None
            self._preview_path = None
        self._draw_preview()

    def _on_copy_code(self, event: tk.Event | None = None) -> None:
        """Copy the selected code's text to the clipboard.

        Args:
            event: Double-click event (unused).

        Returns:
            None
        """
        code = self._selected_code()
        if code is None:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code.text)
        self._set_status(f"コピーしました: {code.text[:60]}")

    # ── processing ───────────────────────────────────

    def add_paths(self, paths: list[Path]) -> None:
        """Add images/folders to the list and start decoding them.

        Args:
            paths: Files and/or folders.

        Returns:
            None
        """
        if self._busy:
            self._set_status("読み取り中です。終わってから追加してください")
            return
        new = [p for p in collect_image_paths(paths) if p not in self._results]
        if not new:
            if paths:
                self._set_status("追加できる新しい画像がありませんでした")
            return
        self._show_drop_hint(False)
        for path in new:
            self._order.append(path)
            self.file_tree.insert(
                "",
                tk.END,
                iid=str(path),
                values=(path.name, "", STATUS_WAITING),
            )
        self._start_worker(new)

    def _start_worker(self, paths: list[Path]) -> None:
        """Decode ``paths`` in a background thread.

        Args:
            paths: Image files to decode.

        Returns:
            None
        """
        self._busy = True
        self._update_buttons()
        self.progress.configure(maximum=len(paths), value=0)

        def work() -> None:
            # read_files is called per file so each result appears in the
            # list as soon as it is ready, instead of after the whole batch.
            for path in paths:
                self._queue.put(("result", read_files([path])[0]))
            self._queue.put(("done", None))

        threading.Thread(target=work, daemon=True).start()
        self.root.after(POLL_MS, self._poll_queue)

    def _poll_queue(self) -> None:
        """Apply results posted by the worker (main thread only).

        Returns:
            None
        """
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            if kind == "result":
                self._apply_result(payload)
            else:
                self._busy = False
                self._update_buttons()
                ordered = [self._results[p] for p in self._order]
                self._set_status(summarize(ordered))
                return
        self.root.after(POLL_MS, self._poll_queue)

    def _apply_result(self, result: FileResult) -> None:
        """Store one file result and refresh its row.

        Args:
            result: Decode result of one file.

        Returns:
            None
        """
        self._results[result.path] = result
        status = file_status(result)
        tags = {STATUS_ERROR: ("error",), STATUS_WARN: ("warn",)}
        self.file_tree.item(
            str(result.path),
            values=(result.path.name, len(result.codes), status),
            tags=tags.get(status, ()),
        )
        self.progress.step(1)
        self._set_status(f"読み取り中… {result.path.name}")
        # Show the first image automatically so the user immediately sees
        # that something happened.
        if not self.file_tree.selection():
            self.file_tree.selection_set(str(result.path))
            self.file_tree.see(str(result.path))
        elif self._preview_path == result.path:
            self._on_file_select()

    # ── display helpers ──────────────────────────────

    def _fill_code_table(self, result: FileResult | None) -> None:
        """Show the codes of one file in the lower table.

        Args:
            result: Decode result, or None if not decoded yet.

        Returns:
            None
        """
        self.code_tree.delete(*self.code_tree.get_children())
        if result is None:
            return
        if result.error:
            self.code_tree.insert(
                "", tk.END, values=("", "", "", result.error)
            )
            return
        if result.warning:
            self.code_tree.insert(
                "",
                tk.END,
                iid="warning",
                values=("", "", "", result.warning),
                tags=("warn",),
            )
        for no, code in enumerate(result.codes, 1):
            # Line breaks would be cut off in a single-line row.
            text = code.text.replace("\r", " ").replace("\n", " ⏎ ")
            self.code_tree.insert(
                "",
                tk.END,
                iid=str(no - 1),
                values=(no, code.format, text, code.note),
                tags=("warn",) if code.note else (),
            )

    def _selected_code(self) -> DecodedCode | None:
        """Return the code selected in the lower table.

        Returns:
            The selected code, or None.
        """
        selection = self.code_tree.selection()
        result = self._results.get(self._preview_path)
        # Only code rows have numeric ids; the warning row has none.
        if not selection or result is None or not selection[0].isdigit():
            return None
        return result.codes[int(selection[0])]

    def _draw_preview(self) -> None:
        """Draw the current image scaled to the canvas with code outlines.

        Returns:
            None
        """
        self.canvas.delete("all")
        if self._preview_img is None:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        img = self._preview_img
        ratio = fit_ratio(img.size, (cw, ch))
        shown = img.resize(
            (max(1, int(img.width * ratio)), max(1, int(img.height * ratio))),
            Image.LANCZOS,
        )
        ox, oy = (cw - shown.width) // 2, (ch - shown.height) // 2
        self._photo = ImageTk.PhotoImage(shown)
        self.canvas.create_image(ox, oy, anchor=tk.NW, image=self._photo)

        result = self._results.get(self._preview_path)
        if result is None:
            return
        selected = self._selected_code()
        for no, code in enumerate(result.codes, 1):
            is_sel = code is selected
            color = BOX_SELECTED_COLOR if is_sel else BOX_COLOR
            flat = [
                v
                for x, y in code.points
                for v in (ox + x * ratio, oy + y * ratio)
            ]
            self.canvas.create_polygon(
                *flat, outline=color, fill="", width=4 if is_sel else 2
            )
            left, top, _, _ = code.bbox
            tx, ty = ox + left * ratio, max(oy + top * ratio - 12, 10)
            self.canvas.create_text(
                tx,
                ty,
                text=f"#{no}",
                fill=color,
                anchor=tk.W,
                font=(
                    font.nametofont("TkDefaultFont").actual("family"),
                    11,
                    "bold",
                ),
            )

    def _show_drop_hint(self, show: bool) -> None:
        """Show or hide the drag-and-drop hint over the file list.

        Args:
            show: True to show.

        Returns:
            None
        """
        if show:
            self.drop_hint.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        else:
            self.drop_hint.place_forget()

    def _update_buttons(self) -> None:
        """Enable or disable buttons according to the current state.

        Returns:
            None
        """
        busy = tk.DISABLED if self._busy else tk.NORMAL
        for btn in (self.btn_add, self.btn_folder, self.btn_clear):
            btn.configure(state=busy)
        has_results = bool(self._results) and not self._busy
        self.btn_save.configure(
            state=tk.NORMAL if has_results else tk.DISABLED
        )

    def _set_status(self, text: str) -> None:
        """Update the status bar message.

        Args:
            text: Message to show.

        Returns:
            None
        """
        self.status_var.set(text)


def main() -> None:
    """Start the GUI application.

    Returns:
        None
    """
    root = TkinterDnD.Tk()
    app = CodeReaderApp(root)
    # Images passed on the command line (e.g. "Send to" or drag onto the
    # .pyw file in Explorer) are loaded right away.
    if len(sys.argv) > 1:
        root.after(100, app.add_paths, [Path(a) for a in sys.argv[1:]])
    root.mainloop()


if __name__ == "__main__":
    main()
