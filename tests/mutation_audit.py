# -*- coding: utf-8 -*-
"""Mutation-testing harness (audit rounds 12-13).

Empirically proves the guard-net catches the historical defect classes:
each mutant re-introduces one real defect, the suite MUST fail, then the
pristine code is restored from an in-memory backup. Nothing is left
modified on disk.

Run on demand (NOT part of the gated build - it lives outside the
test*.py discovery pattern):  python3 tests/mutation_audit.py"""

import subprocess
import sys

MUTANTS = [
    # (label, file, old, new)
    ("M1 security: re-add Administrators localgroup",
     "repair_core/network_repair.py",
     '    runner.note("net_flushdns")',
     '    runner.run(["net", "localgroup", "Administrators",\n'
     '                "NT AUTHORITY\\\\NetworkService", "/add"], timeout=30)\n'
     '    runner.note("net_flushdns")'),
    ("M2 corrupted NTP peer (://windows.com)",
     "repair_core/time_repair.py",
     'NTP_PEERS = "time.windows.com,0x9 time.nist.gov,0x9"',
     'NTP_PEERS = "://windows.com,0x1"'),
    ("M3 w32time config BEFORE re-register (wiped)",
     "repair_core/time_repair.py",
     '    runner.note("time_reregister")',
     '    if service_exists("w32time"):\n'
     '        runner.set_start_mode("w32time", "auto")\n'
     '    runner.note("time_reregister")'),
    ("M4 update structures asymmetry (UsoSvc stop-only)",
     "repair_core/update_repair.py",
     'STOP_ORDER = ["wuauserv", "cryptSvc", "bits", "msiserver", "doSvc"]',
     'STOP_ORDER = ["wuauserv", "cryptSvc", "bits", "msiserver", "doSvc",\n'
     '              "UsoSvc"]'),
    ("M5 dirty volume treated as healthy (no chkdsk /f)",
     "repair_core/disk_repair.py",
     '    if rc == 0:\n'
     '        runner.note("disk_ok")\n'
     '        return {"reboot_required": False}',
     '    if rc in (0, 2):\n'
     '        runner.note("disk_ok")\n'
     '        return {"reboot_required": False}'),
    ("M6 cmd_missing loses the OS reason ({1} dropped)",
     "repair_core/strings.py",
     '"Could not launch command: {0} \u2014 reason: {1}"',
     '"Could not launch command: {0}"'),
    ("M7 SFC decoder: NUL-parity gate disabled",
     "repair_core/system_repair.py",
     "if nulls / (2 * half) > 0.25:",
     "if nulls / (2 * half) > 1.01:"),
    ("M8 rename_dir: collision guard removed",
     "repair_core/runner.py",
     '        counter = 0\n'
     '        while os.path.exists(target):\n'
     '            counter += 1\n'
     '            target = "{0}{1}_{2}_{3}".format(path, suffix, stamp, counter)\n',
     ""),
    ("M9 run_stream: exit code swallowed (always 0)",
     "repair_core/runner.py",
     "            reader.join(timeout=5)\n            return proc.returncode",
     "            reader.join(timeout=5)\n            return 0"),
    ("M10 chkdsk /f timeout dropped to 120s (mid-repair kill)",
     "repair_core/disk_repair.py",
     'result = runner.run(["chkdsk", drive, "/f"], timeout=3600,',
     'result = runner.run(["chkdsk", drive, "/f"], timeout=120,'),
]


def run_suite():
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            capture_output=True, text=True, timeout=300)
        return proc.returncode
    except subprocess.TimeoutExpired:
        # A mutant that HANGS the suite is definitively detected -
        # report it as caught rather than crashing the harness.
        return 124


def main():
    originals = {}
    report = []
    try:
        for label, path, old, new in MUTANTS:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            if old not in src:
                report.append((label, "PATCH-FAILED (anchor missing)"))
                continue
            originals[path] = src
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src.replace(old, new, 1))
            rc = run_suite()
            verdict = ("CAUGHT (suite failed, rc=%d)" % rc) if rc != 0 \
                else "SURVIVED (suite stayed green! GUARD HOLE)"
            report.append((label, verdict))
            with open(path, "w", encoding="utf-8") as fh:  # restore
                fh.write(originals[path])
    finally:
        for path, src in originals.items():  # belt & braces restore
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(src)

    print("\n=== MUTATION REPORT ===")
    holes = 0
    for label, verdict in report:
        print("  %-52s %s" % (label, verdict))
        if not verdict.startswith("CAUGHT"):
            holes += 1
    print("\nmutants: %d | caught: %d | holes: %d"
          % (len(report), len(report) - holes, holes))
    sys.exit(1 if holes else 0)


if __name__ == "__main__":
    main()
