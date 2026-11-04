# -*- coding: utf-8 -*-
"""Windows Update reset - corruption-proof rebuild of the update stack.

Safety model (v1 used `rd /s /q` blindly):
1. Stop the full service chain with *verified* waits (shared svchost
   processes need polling, not fire-and-forget `net stop`).
2. ARCHIVE (rename) SoftwareDistribution and catroot2 to timestamped
   backups instead of hard-deleting: if anything is still locked, the
   rename retries and - if it still fails - we warn and continue instead
   of destroying data mid-write.
3. Clean up archives from *previous* sessions so the disk never fills.
4. Restore stock start modes (demand/trigger - the Win10/11 client
   default) and restart the whole chain in dependency order.
"""

import os

from . import platform_info
from .platform_info import service_exists

# Stop order matters: the update service first, then its dependencies.
STOP_ORDER = ["wuauserv", "cryptSvc", "bits", "msiserver", "doSvc"]
# Start order follows dependencies (crypto -> bits/do -> wuauserv -> msi).
START_ORDER = ["cryptSvc", "bits", "doSvc", "wuauserv", "msiserver"]

# Stock Windows 10/11 client start modes (manual/trigger-start).
START_MODES = {
    "wuauserv": "demand",
    "cryptSvc": "demand",
    "bits": "demand",
    "msiserver": "demand",
    "doSvc": "demand",
}


def _recycle_dir(runner, path):
    """Archive a system directory to a timestamped backup, cleaning older
    backups first. Never hard-deletes a live folder."""
    if not os.path.isdir(path):
        runner.note("dir_missing", (path,))
        return
    runner.cleanup_backups(path)
    target = runner.rename_dir(path)
    if target:
        runner.note("dir_archived", (target,))
    else:
        runner.note("dir_archive_failed", (path,), "warn")


def repair(runner, info=None):
    root = platform_info.systemroot()

    # -- 1. verified stop of the whole update chain -----------------------
    runner.note("upd_stopping")
    existing = [s for s in STOP_ORDER if service_exists(s)]
    for name in existing:
        runner.stop_service(name, timeout=30)
    # A second sweep catches services that only stopped after a dependent
    # released its lock (classic wuauserv/cryptSvc interplay).
    for name in existing:
        runner.stop_service(name, timeout=15)

    # -- 2. archive the corrupt databases ----------------------------------
    _recycle_dir(runner, os.path.join(root, "SoftwareDistribution"))
    _recycle_dir(runner, os.path.join(root, "System32", "catroot2"))

    # -- 3. restore stock start modes ---------------------------------------
    for name, mode in START_MODES.items():
        if service_exists(name):
            runner.set_start_mode(name, mode)

    # -- 4. restart the chain ------------------------------------------------
    runner.note("upd_starting")
    for name in START_ORDER:
        if service_exists(name):
            runner.start_service(name)

    runner.note("upd_rebuilt")
    return {"reboot_required": False}
