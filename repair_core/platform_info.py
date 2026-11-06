"""Platform / edition detection for every Windows 10 and Windows 11 SKU.

Covers: Home, Pro, Pro for Workstations, Enterprise, Education, all LTSC
releases (2015/2016/2019/2021/2024), IoT Enterprise (incl. LTSC), and the
full build range 1507 -> 25H2.  Detection is registry-driven (winreg) so it
costs zero subprocess spawns and never flashes a console window.

Everything degrades gracefully: on non-Windows systems (dev/CI sandboxes)
``detect()`` returns an "unavailable" info object instead of crashing.
"""

# Copyright (c) 2026 alm6iri. All rights reserved.
# Use is governed by the Personal and Internal Use License in LICENSE.
# Commercial redistribution, resale, and sublicensing require written permission.

import os
import shutil

IS_WINDOWS = os.name == "nt"

try:
    import winreg
except ImportError:  # non-Windows dev / CI environments
    winreg = None


# ---------------------------------------------------------------------------
# Build -> marketing-release mapping tables
# ---------------------------------------------------------------------------

_WIN10_RELEASES = {
    10240: "1507",
    10586: "1511",
    14393: "1607",
    15063: "1703",
    16299: "1709",
    17134: "1803",
    17763: "1809",
    18362: "1903",
    18363: "1909",
    19041: "2004",
    19042: "20H2",
    19043: "21H1",
    19044: "21H2",
    19045: "22H2",
}

_WIN11_RELEASES = {
    22000: "21H2",
    22621: "22H2",
    22631: "23H2",
    26100: "24H2",
    26200: "25H2",
}

# Editions that ship as LTSC (Long-Term Servicing Channel).
LTSC_EDITION_IDS = {
    "EnterpriseS",
    "EnterpriseSN",  # LTSC 2015..2024 (+N)
    "IoTEnterpriseS",
    "IoTEnterpriseSN",  # IoT Enterprise LTSC 2021/2024
}

# IoT Enterprise family (value-add of IoT LTSC + regular IoT Enterprise).
IOT_EDITION_IDS = {
    "IoTEnterprise",
    "IoTEnterpriseS",
    "IoTEnterpriseSN",
    "IoTEnterpriseK",
    "IoTEnterpriseSK",
}

_CV_PATH = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"


def release_from_build(build, is_win11):
    """Map a numeric build number to its human release label (pure function,
    fully unit-testable without Windows)."""
    build = int(build or 0)
    table = _WIN11_RELEASES if is_win11 else _WIN10_RELEASES
    if is_win11:
        # Future-proof: unknown Win11 builds above the highest known map to
        # "newer than <highest>" instead of a scary "Unknown".
        known = sorted(table)
        if build > known[-1]:
            return ">" + table[known[-1]]
        return table.get(build, "Insider")
    return table.get(build, "Unknown")


class WindowsInfo:
    """Snapshot of the running Windows SKU."""

    def __init__(self):
        self.available = False  # True only on a real Windows host
        self.product_name = ""  # e.g. "Windows 10 Enterprise LTSC 2021"
        self.edition_id = ""  # e.g. "EnterpriseS", "Core", "Professional"
        self.display_version = ""  # "21H2" / "24H2" (20H2+ / Win11)
        self.release_id = ""  # legacy field (1507 .. 21H2 only)
        self.build = 0
        self.ubr = 0  # Update Build Revision
        self.installation_type = ""  # "Client" / "Server"
        self.is_win11 = False
        self.is_ltsc = False
        self.is_iot = False
        self.is_server = False
        self.arch = ""

    # -- derived helpers ---------------------------------------------------

    @property
    def major(self):
        return 11 if self.is_win11 else 10

    @property
    def build_full(self):
        return f"{self.build}.{self.ubr}" if self.ubr else str(self.build)

    @property
    def release(self):
        """Best available release label, with multiple fallbacks."""
        if self.display_version:
            return self.display_version
        if self.release_id:
            return self.release_id
        if self.build:
            return release_from_build(self.build, self.is_win11)
        return "?"

    def summary(self):
        """One-line, UI-friendly description of the running system."""
        if not self.available:
            return "non-Windows host (development mode)"
        line = " ".join(
            b
            for b in (
                f"Windows {self.major}",
                self.edition_id or "",
                self.release,
            )
            if b
        )
        tags = []
        if self.is_ltsc:
            tags.append("LTSC")
        if self.is_iot:
            tags.append("IoT")
        if self.is_server:
            tags.append("Server")
        if tags:
            line += " [" + "/".join(tags) + "]"
        return f"{line} - Build {self.build_full}" + (
            f" ({self.arch})" if self.arch else ""
        )


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


def _reg_read(name, path=_CV_PATH):
    """Read a string value from the Windows NT CurrentVersion key.
    Returns None on any failure (missing value, permissions, non-Windows)."""
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            value, _kind = winreg.QueryValueEx(key, name)
            return value
    except OSError:
        return None


def _reg_read_int(name, path=_CV_PATH):
    raw = _reg_read(name, path)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect():
    """Detect the running Windows SKU. Safe on every platform."""
    info = WindowsInfo()
    if not IS_WINDOWS or winreg is None:
        return info

    info.product_name = _reg_read("ProductName") or ""
    info.edition_id = _reg_read("EditionID") or ""
    info.display_version = _reg_read("DisplayVersion") or ""
    info.release_id = _reg_read("ReleaseId") or ""
    info.build = _reg_read_int("CurrentBuildNumber")
    info.ubr = _reg_read_int("UBR")
    info.installation_type = _reg_read("InstallationType") or "Client"
    info.arch = os.environ.get("PROCESSOR_ARCHITECTURE", "")

    info.is_win11 = info.build >= 22000
    info.is_ltsc = (
        info.edition_id in LTSC_EDITION_IDS or "LTSC" in info.product_name.upper()
    )
    info.is_iot = info.edition_id in IOT_EDITION_IDS
    info.is_server = (
        "server" in info.installation_type.lower()
        or "server" in info.product_name.lower()
    )
    info.available = True
    return info


def service_exists(name):
    """True when a service/driver key exists under HKLM Services.
    Registry-based (no console spawn, no flicker, works on every build).
    NOTE: unit tests monkeypatch this symbol - keep it module-level."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            rf"SYSTEM\CurrentControlSet\Services\{name}",
        ):
            return True
    except OSError:
        return False


_wmic_cache = None


def has_wmic():
    """WMIC was removed as a FoD in Windows 11 24H2 / Server 2025.
    Probe once, cache the result."""
    global _wmic_cache
    if _wmic_cache is None:
        _wmic_cache = shutil.which("wmic") is not None
    return _wmic_cache


def systemroot():
    """The real Windows directory (never hard-code C:\\Windows - the OS may
    live on another drive)."""
    root = os.environ.get("SystemRoot") or os.path.expandvars(r"%SystemRoot%")
    if not root or not os.path.isdir(root):
        root = r"C:\Windows"
    return root
