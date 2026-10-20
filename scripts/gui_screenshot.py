"""Open the GUI, load the sample images and save a screenshot.

Used to check the layout without clicking by hand. The window is captured
with Tk's own geometry so it works under a virtual display (Xvfb) too.

Usage:
    python scripts/gui_screenshot.py OUTPUT.png
"""

import sys
from pathlib import Path

from PIL import ImageGrab
from tkinterdnd2 import TkinterDnD

from code_reader.gui import CodeReaderApp

SAMPLES_DIR = Path(__file__).parent / "samples"


def capture(root: TkinterDnD.Tk, out: Path) -> None:
    """Save the window area of the screen to ``out`` and close the app.

    Args:
        root: Tk root window.
        out: Output PNG path.

    Returns:
        None
    """
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(out)
    root.destroy()


def main() -> None:
    """Run the scripted session.

    Returns:
        None
    """
    out = Path(sys.argv[1])
    root = TkinterDnD.Tk()
    app = CodeReaderApp(root)
    app.add_paths([SAMPLES_DIR])

    def select_first_code() -> None:
        # Selecting a row shows the orange highlight in the preview.
        app.file_tree.selection_set(str(SAMPLES_DIR / "02_photo_like.jpg"))
        root.update()
        app.code_tree.selection_set("1")
        root.after(500, capture, root, out)

    # Sample decoding takes about a second; wait generously.
    root.after(4000, select_first_code)
    root.mainloop()


if __name__ == "__main__":
    main()
