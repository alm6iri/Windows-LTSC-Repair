"""Windows LTSC Repair Tool - core engine package.

This package contains all platform-independent (testable) repair logic:
platform detection, a safe command runner, per-domain repair modules,
localization strings and an event log store.  The GUI lives in FixTool.py
and only *consumes* this package, which keeps every command decision
unit-testable on any OS.
"""

__version__ = "2.3.1"
__all__ = [
    "disk_repair",
    "eventlog",
    "network_repair",
    "platform_info",
    "runner",
    "strings",
    "system_repair",
    "time_repair",
    "update_repair",
]
