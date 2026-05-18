# PyInstaller spec — builds OrderTracker.exe + updater_runner.exe.
# Run via: pyinstaller scripts/ordertracker.spec --noconfirm

# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = Path(SPECPATH).parent  # type: ignore[name-defined]

hidden_imports = (
    collect_submodules("ordertracker")
    + collect_submodules("sqlalchemy.dialects")
    + ["psycopg", "psycopg.types.json"]
)
data_files = (
    collect_data_files("ordertracker", subdir="i18n")
    + collect_data_files("ordertracker", subdir="ui/styles")
)

block_cipher = None

main_analysis = Analysis(  # type: ignore[name-defined]
    ["../src/ordertracker/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=data_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    cipher=block_cipher,
)
main_pyz = PYZ(main_analysis.pure, main_analysis.zipped_data, cipher=block_cipher)  # type: ignore[name-defined]
main_exe = EXE(  # type: ignore[name-defined]
    main_pyz,
    main_analysis.scripts,
    [],
    exclude_binaries=True,
    name="OrderTracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

updater_analysis = Analysis(  # type: ignore[name-defined]
    ["../src/ordertracker/updater/runner.py"],
    pathex=["../src"],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=["tkinter"],
)
updater_pyz = PYZ(updater_analysis.pure, updater_analysis.zipped_data, cipher=block_cipher)  # type: ignore[name-defined]
updater_exe = EXE(  # type: ignore[name-defined]
    updater_pyz,
    updater_analysis.scripts,
    [],
    exclude_binaries=True,
    name="updater_runner",
    debug=False,
    console=True,
)

coll = COLLECT(  # type: ignore[name-defined]
    main_exe,
    main_analysis.binaries,
    main_analysis.zipfiles,
    main_analysis.datas,
    updater_exe,
    updater_analysis.binaries,
    updater_analysis.zipfiles,
    updater_analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="OrderTracker",
)
