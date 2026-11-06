"""Time synchronization repair.

v1 shipped a corrupted peer list (`://windows.com` - an invalid host that
guaranteed resync failure). v2 uses the vendor-recommended primary
(time.windows.com, client mode + special interval = 0x9) with NIST as a
redundant fallback peer, re-registers the w32time service and retries
the resync (the first attempt frequently fails while the service warms
up), then dumps the resulting sync status into the event log.
"""

import time

from .platform_info import service_exists

# 0x9 = 0x8 (client mode) | 0x1 (special interval) - Windows default.
NTP_PEERS = "time.windows.com,0x9 time.nist.gov,0x9"


def repair(runner, info=None):
    if service_exists("w32time"):
        runner.note("time_stopping")
        runner.stop_service("w32time", timeout=15)

    runner.note("time_reregister")
    runner.run(["w32tm", "/unregister"], timeout=60)
    time.sleep(1.0)
    runner.run(["w32tm", "/register"], timeout=60)
    time.sleep(1.0)

    # IMPORTANT: the start mode must be configured AFTER /register -
    # `w32tm /unregister` deletes the service registration (wiping any
    # earlier sc config) and /register recreates it with the stock
    # Manual start type. Configuring before the re-register was a silent
    # no-op in earlier revisions.
    if service_exists("w32time"):
        runner.set_start_mode("w32time", "auto")

    if not runner.start_service("w32time", wait=15, retries=2):
        runner.note("time_service_failed", (), "warn")
        return {"reboot_required": False}

    runner.note("time_config")
    runner.run(
        [
            "w32tm",
            "/config",
            "/manualpeerlist:" + NTP_PEERS,
            "/syncfromflags:manual",
            "/reliable:no",
            "/update",
        ],
        timeout=60,
    )

    # First resync often fails while peers are being resolved - retry.
    synced = False
    for attempt in range(3):
        result = runner.run(["w32tm", "/resync", "/force"], timeout=90)
        if result.ok:
            synced = True
            break
        time.sleep(3.0)

    if synced:
        runner.note("time_resynced", (NTP_PEERS.split()[0].split(",")[0],))
    else:
        runner.note("time_resync_failed", (), "warn")

    status = runner.run(["w32tm", "/query", "/status"], timeout=30, report=False)
    if status.ok and status.out:
        for line in status.out.splitlines():
            line = line.strip()
            if line:
                runner.raw("    " + line)

    return {"reboot_required": False}
