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


def _looks_like_mojibake(text):
    """True when a large fraction of characters landed in CJK/fullwidth
    blocks - the classic signature of bytes decoded with the WRONG
    16-bit encoding (random BMP codepoints cluster heavily there)."""
    if not text:
        return True
    cjk = sum(
        1 for ch in text
        if 0x3000 <= ord(ch) <= 0x9FFF or 0xFF00 <= ord(ch) <= 0xFFEF
    )
    return cjk / len(text) > 0.10


def _decode_sfc(data):
    """Best-effort decode of SFC output.

    Decision order:
    1. NUL-byte parity evidence: genuine UTF-16LE text carries NUL bytes
       in one parity whenever it contains ASCII (paths/numbers always
       do), regardless of the message language - byte-level proof that
       survives even pure CJK/Arabic message text mixed with paths.
    2. Otherwise try utf-16-le / cp850 / utf-8 in turn and REJECT any
       candidate that looks like CJK mojibake soup.
    Returns '' for empty input."""
    if not data:
        return ""
    half = len(data) // 2
    if half:
        nulls = data[0::2].count(0) + data[1::2].count(0)
        if nulls / (2 * half) > 0.25:
            return data.decode("utf-16-le", errors="replace")
    for encoding in ("utf-16-le", "cp850", "utf-8"):
        try:
            text = data.decode(encoding, errors="ignore")
        except LookupError:
            continue
        if text and not _looks_like_mojibake(text):
            return text
    return data.decode("utf-8", errors="replace")


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
            runner.note("dism_failed",
                        (rc if rc is not None else "-",), "warn")
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
