# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the QR / barcode reader GUI.

Usage:
    pyinstaller --noconfirm code_reader.spec

Output:
    dist/CodeReader/CodeReader.exe  (copy the whole dist/CodeReader folder)

Notes:
    - tkinterdnd2 (tkdnd DLLs) and ttkbootstrap (theme assets) are collected
      by the hooks shipped with pyinstaller-hooks-contrib and ttkbootstrap,
      so no manual datas/binaries are listed here.
    - One-folder mode is used instead of one-file: it starts faster (no
      unpacking to a temp folder on every launch) and is less often flagged
      by antivirus software.
"""

a = Analysis(
    ["run_gui.pyw"],
    pathex=["."],
    binaries=[],
    datas=[],
    # ImageTk imports this lazily when Tk first needs a PIL image (the
    # ttkbootstrap theme does), so PyInstaller cannot see it. Missing it
    # crashed the trial build with "No module named PIL._tkinter_finder".
    hiddenimports=["PIL._tkinter_finder"],
    hookspath=[],
    runtime_hooks=[],
    # Test and trial-only packages are not needed at runtime.
    excludes=["pytest", "pyzbar", "segno", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CodeReader",
    debug=False,
    strip=False,
    upx=False,
    # GUI app: no console window behind the main window.
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CodeReader",
)
