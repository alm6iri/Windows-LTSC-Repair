"""Disk health verification & repair (CHKDSK + SMART) - new in v2.1.

Safety-first design, compatible with every SKU from 1507 to 25H2:

1. SMART health of physical disks via ``Get-PhysicalDisk`` (best-effort:
   unavailable on many VMs and older storage stacks - degrades to a note).
2. Online read-only verification of the SYSTEM volume with
   ``chkdsk <drive> /scan`` (no dismount, no reboot, Win8+ semantics).
3. Only when the scan reports unrepaired problems is an *offline* fix
   (``chkdsk /f``) scheduled for the next reboot - answering the Y/N
   prompt programmatically. Nothing destructive ever runs online.

Exit-code classification (Microsoft-documented):
  0 -> no errors; 1 -> errors fixed; 2 -> errors found (dirty volume);
  3+ -> errors that could not be fixed.
"""

import ntpath

from . import platform_info

# FriendlyName | HealthStatus per physical disk (Healthy/Warning/Unhealthy)
_PS_SMART = (
    "Get-PhysicalDisk -ErrorAction SilentlyContinue | "
    "ForEach-Object { '{0} | {1}' -f $_.FriendlyName, $_.HealthStatus }"
)


def _powershell(runner, script, timeout=120):
    return runner.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        timeout=timeout,
    )


def system_drive():
    """The drive hosting Windows (e.g. 'C:'), derived from %SystemRoot% -
    never assumes C:. Uses ntpath semantics on every platform."""
    drive = ntpath.splitdrive(platform_info.systemroot())[0]
    return drive or "C:"


def _smart_report(runner):
    runner.note("disk_smart")
    result = _powershell(runner, _PS_SMART, timeout=120)
    if result.ok and (result.out or "").strip():
        for line in result.out.splitlines():
            line = line.strip()
            if line:
                runner.raw("    " + line)
    else:
        # Common on VMs / LTSC images without the Storage module.
        runner.note("disk_smart_na", (), "warn")


def repair(runner, info=None):
    drive = system_drive()
    runner.note("sys_drive", (drive,))
    _smart_report(runner)

    # ---- online verification (safe, no dismount) -------------------------
    runner.note("disk_scan_start")
    rc = runner.run_stream(
        ["chkdsk", drive, "/scan"],
        timeout=3600,
        on_line=lambda line: runner.raw("    " + line),
    )
    if rc is None:
        runner.note("disk_failed", ("-",), "warn")
        return {"reboot_required": False}

    if rc == 0:
        runner.note("disk_ok")
        return {"reboot_required": False}
    if rc == 1:
        runner.note("disk_fixed")
        return {"reboot_required": False}

    # ---- errors found: schedule the offline fix for next reboot ----------
    runner.note("disk_errors")
    # Long timeout on purpose: if the volume happens to be lockable,
    # chkdsk /f runs the FULL repair immediately - killing it mid-fix
    # (a 120s timeout would) risks filesystem corruption.
    result = runner.run(["chkdsk", drive, "/f"], timeout=3600, input="Y\r\n")
    if result.ok:
        runner.note("disk_scheduled", (drive,))
        return {"reboot_required": True}
    runner.note("disk_failed", (result.rc if result.rc is not None else "-",), "warn")
    return {"reboot_required": False}
