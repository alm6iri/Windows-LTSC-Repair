# -*- coding: utf-8 -*-
"""Deep network stack repair for all Windows 10/11 editions.

Compatibility strategy:
* ``Enable-NetAdapter`` (PowerShell NetAdapter module, present since Win8)
  is the primary adapter re-enabler; ``wmic`` is only used as a fallback
  on builds where it still exists, because WMIC is removed in 24H2.
* Service configuration is registry-gated: only services that actually
  exist on this SKU get configured (CDPSvc / NcdAutoSetup are absent on
  LTSC, WlanSvc is absent on desktops without WLAN, etc.).
* SECURITY: unlike v1, this module never modifies local groups
  (the old `net localgroup Administrators NetworkService` was a severe
  privilege-escalation misconfiguration and has been removed entirely).
"""

import os

from . import platform_info
from .platform_info import service_exists

# (service, start mode) - applied only when the service exists on this SKU.
SERVICE_MODES = [
    ("NlaSvc", "auto"),        # Network Location Awareness
    ("Dhcp", "auto"),          # DHCP Client
    ("Dnscache", "auto"),      # DNS Client
    ("nsi", "auto"),           # Network Store Interface
    ("netprofm", "demand"),    # Network List Service
    ("NcbService", "demand"),  # Network Connection Broker
    ("NetSetupSvc", "demand"), # Network Setup Service
    ("NcdAutoSetup", "demand"),# Network Connectivity Assistant (non-LTSC)
    ("CDPSvc", "auto"),        # Connected Devices Platform (non-LTSC)
    ("WlanSvc", "auto"),       # WLAN AutoConfig (wireless-capable SKUs)
]

_PS_ENABLE_ADAPTERS = (
    "Get-NetAdapter -Physical -ErrorAction SilentlyContinue | "
    "Where-Object { $_.Status -eq 'Disabled' } | "
    "Enable-NetAdapter -Confirm:$false -ErrorAction SilentlyContinue"
)

_PS_APPX_PROBE = (
    "if (Get-AppxPackage -Name 'Microsoft.Windows.ShellExperienceHost' "
    "-ErrorAction SilentlyContinue) { 'found' } else { 'none' }"
)

_PS_APPX_REGISTER = (
    "Get-AppxPackage -AllUsers -Name 'Microsoft.Windows.ShellExperienceHost' "
    "-ErrorAction SilentlyContinue | ForEach-Object { "
    "Add-AppxPackage -DisableDevelopmentMode -Register "
    "(Join-Path $_.InstallLocation 'AppXManifest.xml') "
    "-ErrorAction SilentlyContinue }"
)


def _powershell(runner, script, timeout=180):
    return runner.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        timeout=timeout,
    )


def _enable_adapters(runner):
    """Re-enable physically-present but disabled NICs.
    PowerShell first (works on every build incl. 24H2), WMIC fallback."""
    result = _powershell(runner, _PS_ENABLE_ADAPTERS, timeout=180)
    if result.ok:
        return
    # PowerShell path failed (rare, e.g. PS remoting broken) - try WMIC
    # only on builds where it still exists.
    if platform_info.has_wmic():
        runner.run(
            ["wmic", "path", "win32_networkadapter",
             "where", "PhysicalAdapter=True", "call", "enable"],
            timeout=120,
        )
    else:
        runner.note("adapters_probe_failed", (), "warn")


def _fix_services(runner):
    """Restore stock service configuration - gated by existence checks."""
    for name, mode in SERVICE_MODES:
        if not service_exists(name):
            runner.note("service_missing", (name,))
            continue
        runner.set_start_mode(name, mode)
        if mode == "auto":
            runner.start_service(name)


def _reregister_appx(runner):
    """Re-register the Shell Experience Host (fixes broken Start menu /
    tray). Skipped automatically on SKUs without Appx payloads (LTSC)."""
    probe = _powershell(runner, _PS_APPX_PROBE, timeout=120)
    if probe.ok and "found" in (probe.out or "").lower():
        runner.note("appx_register")
        _powershell(runner, _PS_APPX_REGISTER, timeout=300)
    else:
        # LTSC / stripped images have no ShellExperienceHost - expected.
        runner.note("appx_skip")


def repair(runner, info=None):
    """Full network stack rebuild. Requires a reboot to complete."""
    root = platform_info.systemroot()

    runner.note("net_winsock")
    runner.run(["netsh", "winsock", "reset"], timeout=60)

    runner.note("net_ip_reset")
    runner.run(
        ["netsh", "int", "ip", "reset",
         os.path.join(root, "resetlog_netsh_ip.txt")],
        timeout=60,
    )

    runner.note("net_flushdns")
    runner.run(["ipconfig", "/flushdns"], timeout=60)

    _enable_adapters(runner)
    _fix_services(runner)
    _reregister_appx(runner)

    return {"reboot_required": True}
