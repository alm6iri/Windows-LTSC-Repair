# -*- coding: utf-8 -*-
"""Windows LTSC Repair Tool - core engine package.

This package contains all platform-independent (testable) repair logic:
platform detection, a safe command runner, per-domain repair modules,
localization strings and an event log store.  The GUI lives in FixTool.py
and only *consumes* this package, which keeps every command decision
unit-testable on any OS.
"""

__version__ = "2.3.1"
__all__ = [
    "platform_info",
    "runner",
    "network_repair",
    "update_repair",
    "time_repair",
    "system_repair",
    "disk_repair",
    "strings",
    "eventlog",
]
