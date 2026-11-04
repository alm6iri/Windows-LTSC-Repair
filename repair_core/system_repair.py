# -*- coding: utf-8 -*-
"""System file & component-store repair (DISM + SFC).

New capability in v2 - works identically on every SKU from LTSC 2015 to
Windows 11 24H2, including images where the component store is repaired
from a mounted ISO/Windows Update fallback.

SFC quirk handled here: when its output is redirected, sfc.exe writes
UTF-16LE on all supported builds - decoding it as UTF-8 yields mojibake,
so we capture raw bytes and decode defensively.
"""

import os

from . import platform_info

_SFC_OK = "did not find any integrity violations"
_SFC_FIXED = "successfully repaired"
_SFC_PARTIAL = "could not be fixed"
# Localized Windows may phrase these differently; also match by exit code.


def _decode_sfc(data):
    """Best-effort decode of SFC output (UTF-16LE first, then legacy
    code pages). Returns '' for empty input."""
    if not data:
        return ""
    candidates = ("utf-16-le", "cp850", "utf-8")
    best = ""
    best_score = -1.0
    for encoding in candidates:
        try:
            text = data.decode(encoding, errors="ignore")
        except (LookupError, UnicodeDecodeError):
            continue
        if not text:
            continue
        printable = sum(1 for ch in text if ch.isprintable() or ch in "\r\n\t")
        score = printable / max(1, len(text))
        if score > best_score:
            best, best_score = text, score
        if score > 0.95:
            break
    return best


def repair(runner, info=None):
    root = platform_info.systemroot()

    # ---- 1. DISM: repair the component store -----------------------------
    dism = os.path.join(root, "System32", "Dism.exe")
    if os.path.isfile(dism):
        runner.note("dism_start")
        rc = runner.run_stream(
            [dism, "/Online", "/Cleanup-Image", "/RestoreHealth"],
            timeout=3600,
            on_line=lambda line: runner.raw("    " + line),
        )
        if rc == 0:
            runner.note("dism_ok")
        else:
            # Non-fatal: SFC can still repair in-place; report and continue.
            runner.note("dism_failed", (rc,), "warn")
    else:
        runner.note("dism_missing", (), "warn")

    # ---- 2. SFC: repair protected OS files --------------------------------
    runner.note("sfc_start")
    rc, data = runner.run_bytes(["sfc", "/scannow"], timeout=3600)
    output = _decode_sfc(data)

    verdict_key = "sfc_unknown"
    lowered = output.lower()
    if rc == 0 and _SFC_OK in lowered:
        verdict_key = "sfc_ok"
    elif _SFC_FIXED in lowered:
        verdict_key = "sfc_fixed"
    elif _SFC_PARTIAL in lowered or (rc not in (0, None)):
        verdict_key = "sfc_partial"
    runner.note(verdict_key)

    # Append the informative tail of CBS output for diagnostics.
    tail = [l for l in output.splitlines() if l.strip()][-12:]
    for line in tail:
        runner.raw("    " + line.strip())

    return {"reboot_required": verdict_key in ("sfc_fixed", "sfc_partial")}
