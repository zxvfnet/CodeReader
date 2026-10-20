"""Expand user-selected files/folders and decode them in a batch."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from code_reader.decoder import (
    MAX_SYMBOLS_PER_PASS,
    DecodedCode,
    decode_image,
)

NOTE_LIMIT = (
    f"要確認：検出数が上限（{MAX_SYMBOLS_PER_PASS}個）に達したため、"
    "読み漏れの可能性があります"
)
IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
)


@dataclass
class FileResult:
    """Decode result of one image file.

    Attributes:
        path: Image file path.
        codes: Codes found in the image (may be empty).
        error: Error message when the file could not be read, else "".
        warning: File-level warning (e.g. detection limit reached), else "".
    """

    path: Path
    codes: list[DecodedCode] = field(default_factory=list)
    error: str = ""
    warning: str = ""


def collect_image_paths(paths: Iterable[Path]) -> list[Path]:
    """Expand files and folders into a sorted, de-duplicated image list.

    Folders are searched only one level deep so that dropping a large folder
    does not unexpectedly scan its whole subtree.

    Args:
        paths: Files and/or folders chosen by the user.

    Returns:
        Image file paths with a known image suffix, sorted by path.
        Files explicitly given are kept even if their suffix is unknown,
        because the user chose them on purpose; reading will report errors.
    """
    found: set[Path] = set()
    for path in paths:
        if path.is_dir():
            found.update(
                p
                for p in path.iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
            )
        elif path.is_file():
            found.add(path)
    return sorted(found)


def load_image(path: Path) -> Image.Image:
    """Load an image fully into memory.

    Args:
        path: Image file path (non-ASCII paths are supported).

    Returns:
        The loaded image.

    Raises:
        OSError: If the file is missing or not a readable image.
    """
    with Image.open(path) as img:
        # load() inside the with block so the file handle is released and
        # the user can move/delete the file while the app keeps the image.
        img.load()
        return img.copy()


def read_files(
    paths: Iterable[Path],
    on_progress: Callable[[int, int, Path], None] | None = None,
) -> list[FileResult]:
    """Decode every image and collect per-file results.

    One broken file must not stop a batch of hundreds, so read errors are
    recorded on the result instead of being raised.

    Args:
        paths: Image file paths (already expanded).
        on_progress: Optional callback called before each file with
            (index starting at 1, total, path), used by the GUI progress bar.

    Returns:
        One FileResult per path, in the given order.
    """
    path_list = list(paths)
    results = []
    for index, path in enumerate(path_list, 1):
        if on_progress is not None:
            on_progress(index, len(path_list), path)
        try:
            codes = decode_image(load_image(path))
        # OSError covers missing, unreadable and non-image files
        # (UnidentifiedImageError is a subclass); huge images raise
        # DecompressionBombError, which is not an OSError.
        except (OSError, Image.DecompressionBombError) as exc:
            results.append(
                FileResult(path, error=f"画像を読み込めません: {exc}")
            )
            continue
        # Reaching the cap means the decoder may have stopped early, and the
        # user cannot tell missing codes apart from absent ones otherwise.
        limit_hit = len(codes) >= MAX_SYMBOLS_PER_PASS
        results.append(
            FileResult(path, codes, warning=NOTE_LIMIT if limit_hit else "")
        )
    return results
