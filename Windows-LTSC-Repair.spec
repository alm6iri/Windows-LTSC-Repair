# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller release specification for Windows-LTSC-Repair.

Produces a single standalone executable:

    dist/Windows-LTSC-Repair.exe

Key properties (validated by the release pipeline):
  * onefile  - one clean EXE, no sidecar DLL folders
  * windowed - no console flash (the core runner already uses
               CREATE_NO_WINDOW for every subprocess)
  * uac_admin - embeds a `requireAdministrator` requestedExecutionLevel
               manifest, so the EXE always prompts UAC on launch
  * icon      - multi-resolution app_icon.ico (16..256px, 32bpp)
  * datas     - customtkinter theme/data assets are collected explicitly
               (protects against PyInstaller versions without the
               customtkinter hook), and the repair_core package is
               pinned as a hidden import so it is never tree-shaken.

Build on a Windows host (PyInstaller does not cross-compile):

    python -m PyInstaller --noconfirm --clean Windows-LTSC-Repair.spec
"""

import os

from PyInstaller.utils.hooks import collect_data_files

PROJECT_ROOT = SPECPATH  # directory containing this spec file

# customtkinter ships JSON theme assets that MUST be bundled; collect
# them explicitly instead of relying on hooks-contrib being present.
ctk_datas = collect_data_files("customtkinter", include_py_files=False)
# Ship the window icon inside the bundle too: the GUI looks it up under
# sys._MEIPASS at runtime (spec-driven onefile builds never depend on
# sidecar files).
ctk_datas.append((os.path.join(PROJECT_ROOT, "app_icon.ico"), "."))

a = Analysis(
    ["FixTool.py"],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=ctk_datas,
    hiddenimports=[
        "repair_core",
        "repair_core.platform_info",
        "repair_core.runner",
        "repair_core.network_repair",
        "repair_core.update_repair",
        "repair_core.time_repair",
        "repair_core.system_repair",
        "repair_core.disk_repair",
        "repair_core.strings",
        "repair_core.eventlog",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Windows-LTSC-Repair",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, "app_icon.ico"),
    uac_admin=True,         # requireAdministrator UAC manifest
)
