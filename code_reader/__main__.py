"""Command-line entry point for checking the reader without the GUI.

Usage:
    python -m code_reader IMAGE_OR_FOLDER [...] -o result.csv
"""

import argparse
import sys
from pathlib import Path

from code_reader.files import collect_image_paths, read_files
from code_reader.csv_writer import write_csv


def main(argv: list[str] | None = None) -> int:
    """Decode the given images/folders and write a CSV file.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code: 0 on success, 1 when no image was found.
    """
    parser = argparse.ArgumentParser(
        description="画像内のQRコード・バーコードをCSVに出力します。"
    )
    parser.add_argument(
        "inputs", nargs="+", type=Path, help="画像ファイルまたはフォルダ"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("result.csv"),
        help="出力CSVファイル",
    )
    args = parser.parse_args(argv)

    paths = collect_image_paths(args.inputs)
    if not paths:
        print("画像ファイルが見つかりません。", file=sys.stderr)
        return 1
    results = read_files(
        paths, on_progress=lambda i, n, p: print(f"[{i}/{n}] {p.name}")
    )
    rows = write_csv(results, args.output)
    codes = sum(len(r.codes) for r in results)
    print(
        f"{codes} 件のコードを検出し、{rows} 行を {args.output} に出力しました。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
