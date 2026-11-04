# -*- coding: utf-8 -*-
"""Unit tests for the repair_core engine.

Runs on ANY OS (Linux CI included): Windows specifics are mocked, so the
repair *decisions* - which command runs, in what order, with what gating -
are verified without touching a real system.

Run:  python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repair_core import (network_repair, update_repair, time_repair,
                         disk_repair, platform_info, strings as strings_mod,
                         eventlog)
from repair_core.runner import CmdResult, fmt_cmd


class FakeRunner(object):
    """Records every call the repair modules make - no real commands run."""

    def __init__(self, outcomes=None):
        self.calls = []
        self.notes = []
        self.raws = []
        self._outcomes = outcomes or {}

    def note(self, key, params=(), level="info"):
        self.notes.append((key, tuple(params), level))

    def raw(self, text, level="info"):
        self.raws.append(text)

    def run(self, cmd, timeout=120, report=True, input=None):
        self.calls.append(("run", tuple(cmd)))
        outcome = self._outcomes.get(tuple(cmd))
        if outcome is None:
            outcome = (0, "", "")
        return CmdResult(outcome[0], outcome[1], outcome[2])

    def run_stream(self, cmd, timeout=3600, on_line=None):
        self.calls.append(("run_stream", tuple(cmd)))
        return getattr(self, "_stream_rc", 0)

    def run_bytes(self, cmd, timeout=3600):
        self.calls.append(("run_bytes", tuple(cmd)))
        return 0, b"\xff\xfe" + "did not find any integrity violations".encode("utf-16-le")

    def service_state(self, name):
        return "RUNNING"

    def stop_service(self, name, timeout=30):
        self.calls.append(("stop", name))
        return True

    def start_service(self, name, wait=15, retries=1):
        self.calls.append(("start", name))
        return True

    def set_start_mode(self, name, mode):
        self.calls.append(("config", name, mode))
        return True

    def rename_dir(self, path, suffix=".bak"):
        self.calls.append(("rename", path))
        return path + ".bak_TEST"

    def delete_path(self, path):
        self.calls.append(("delete", path))
        return True

    def cleanup_backups(self, path, suffix=".bak"):
        self.calls.append(("cleanup", path))
        return 0

    # -- assertion helpers --
    def all_text(self):
        chunks = []
        for call in self.calls:
            chunks.extend(str(part) for part in call)
        return " ".join(chunks)


class TestStrings(unittest.TestCase):
    def test_ar_en_key_symmetry(self):
        ar = set(strings_mod.STRINGS["AR"])
        en = set(strings_mod.STRINGS["EN"])
        self.assertEqual(ar, en, "missing translations: %s / %s"
                         % (ar - en, en - ar))

    def test_render_placeholders(self):
        out = strings_mod.render(strings_mod.STRINGS["EN"],
                                 "cmd_failed", (5, "sc start x"))
        self.assertIn("5", out)
        self.assertIn("sc start x", out)

    def test_render_unknown_key_never_crashes(self):
        self.assertEqual(strings_mod.render(strings_mod.STRINGS["EN"], "nope"), "nope")


class TestPlatformInfo(unittest.TestCase):
    def test_win10_release_mapping(self):
        self.assertEqual(platform_info.release_from_build(10240, False), "1507")
        self.assertEqual(platform_info.release_from_build(19045, False), "22H2")

    def test_win11_release_mapping(self):
        self.assertEqual(platform_info.release_from_build(22000, True), "21H2")
        self.assertEqual(platform_info.release_from_build(26100, True), "24H2")

    def test_future_win11_build_is_not_unknown(self):
        self.assertEqual(platform_info.release_from_build(30000, True), ">24H2")

    def test_summary_flags_ltsc_and_iot(self):
        info = platform_info.WindowsInfo()
        info.available = True
        info.build, info.ubr = 26100, 1
        info.is_win11 = True
        info.edition_id = "IoTEnterpriseS"
        info.is_ltsc = True
        info.is_iot = True
        summary = info.summary()
        self.assertIn("LTSC", summary)
        self.assertIn("IoT", summary)
        self.assertIn("26100", summary)

    def test_detect_on_non_windows_does_not_crash(self):
        info = platform_info.detect()
        self.assertFalse(info.available)
        self.assertIn("non-Windows", info.summary())


class TestNetworkRepair(unittest.TestCase):
    def test_security_never_touches_local_groups(self):
        """REGRESSION (security): v1 added NetworkService/LocalService to
        the Administrators group - a privilege-escalation misconfiguration.
        This test makes sure it can never come back."""
        runner = FakeRunner()
        with mock.patch.object(network_repair, "service_exists",
                               return_value=True):
            network_repair.repair(runner, None)
        blob = runner.all_text().lower()
        self.assertNotIn("localgroup", blob)
        self.assertNotIn("administrators", blob)

    def test_core_resets_and_adapter_enable_via_powershell(self):
        runner = FakeRunner()
        with mock.patch.object(network_repair, "service_exists",
                               return_value=True):
            result = network_repair.repair(runner, None)
        blob = runner.all_text()
        self.assertIn("netsh", blob)
        self.assertIn("winsock", blob)
        self.assertIn("ipconfig", blob)
        # PowerShell adapter path (WMIC-free - required for 24H2).
        self.assertIn("Enable-NetAdapter", blob)
        self.assertNotIn("wmic", blob.lower())
        self.assertTrue(result["reboot_required"])

    def test_missing_services_are_skipped_not_blindly_configured(self):
        runner = FakeRunner()
        existing = {"NlaSvc", "Dhcp", "nsi"}  # LTSC-like service set
        with mock.patch.object(network_repair, "service_exists",
                               side_effect=lambda n: n in existing):
            network_repair.repair(runner, None)
        configured = {c[1] for c in runner.calls if c[0] == "config"}
        self.assertEqual(configured, existing)
        skipped = [n[1][0] for n in runner.notes if n[0] == "service_missing"]
        self.assertIn("CDPSvc", skipped)   # absent on LTSC
        self.assertIn("WlanSvc", skipped)

    def test_appx_skipped_when_package_absent(self):
        runner = FakeRunner()
        probe = ("powershell.exe", "-NoProfile", "-ExecutionPolicy",
                 "Bypass", "-Command",
                 network_repair._PS_APPX_PROBE)
        runner._outcomes[probe] = (0, "none", "")
        with mock.patch.object(network_repair, "service_exists",
                               return_value=True):
            network_repair.repair(runner, None)
        self.assertIn("appx_skip", [n[0] for n in runner.notes])


class TestUpdateRepair(unittest.TestCase):
    def _run(self, runner):
        services = {"wuauserv", "cryptSvc", "bits", "msiserver", "doSvc"}
        with mock.patch.object(update_repair, "service_exists",
                               side_effect=lambda n: n in services), \
             mock.patch("os.path.isdir", return_value=True), \
             mock.patch.object(update_repair.platform_info, "systemroot",
                               return_value="X:\\Windows"):
            return update_repair.repair(runner, None)

    def test_stop_archive_rebuild_flow(self):
        runner = FakeRunner()
        result = self._run(runner)

        stopped = [c[1] for c in runner.calls if c[0] == "stop"]
        self.assertEqual(stopped, ["wuauserv", "cryptSvc", "bits",
                                   "msiserver", "doSvc",
                                   # second verified sweep:
                                   "wuauserv", "cryptSvc", "bits",
                                   "msiserver", "doSvc"])
        renamed = [c[1] for c in runner.calls if c[0] == "rename"]
        self.assertEqual(
            renamed,
            [os.path.join("X:\\Windows", "SoftwareDistribution"),
             os.path.join("X:\\Windows", "System32", "catroot2")])
        # Never a hard delete of the live folders (rd /s /q is gone).
        deleted = [c[1] for c in runner.calls if c[0] == "delete"]
        self.assertEqual(deleted, [])
        modes = {c[1]: c[2] for c in runner.calls if c[0] == "config"}
        self.assertEqual(modes["wuauserv"], "demand")
        started = [c[1] for c in runner.calls if c[0] == "start"]
        self.assertEqual(started[0], "cryptSvc")  # dependency order
        self.assertFalse(result["reboot_required"])

    def test_locked_directory_degrades_to_warning(self):
        runner = FakeRunner()
        runner.rename_dir = lambda path, suffix=".bak": None  # locked
        self._run(runner)
        self.assertIn("dir_archive_failed",
                      [n[0] for n in runner.notes])


class TestTimeRepair(unittest.TestCase):
    def test_peer_list_is_valid(self):
        """REGRESSION: v1 shipped the corrupted peer `://windows.com`."""
        runner = FakeRunner()
        with mock.patch.object(time_repair, "service_exists",
                               return_value=True):
            time_repair.repair(runner, None)
        blob = runner.all_text()
        self.assertNotIn("://windows.com", blob)
        self.assertIn("time.windows.com,0x9", blob)
        self.assertIn("/resync", blob)
        self.assertIn("w32tm", blob)

    def test_resync_retries_then_reports_failure(self):
        runner = FakeRunner()
        resync = ("w32tm", "/resync", "/force")
        runner._outcomes[resync] = (1, "", "Access denied")
        with mock.patch.object(time_repair, "service_exists",
                               return_value=True), \
             mock.patch.object(time_repair.time, "sleep", lambda s: None):
            time_repair.repair(runner, None)
        resync_count = sum(1 for c in runner.calls
                           if c[0] == "run" and c[1] == resync)
        self.assertEqual(resync_count, 3)
        self.assertIn("time_resync_failed",
                      [n[0] for n in runner.notes if n[2] == "warn"])


class TestDiskRepair(unittest.TestCase):
    def _run(self, runner):
        with mock.patch.object(disk_repair.platform_info, "systemroot",
                               return_value="D:\\Windows"):
            return disk_repair.repair(runner, None)

    def test_healthy_volume_never_schedules_offline_fix(self):
        runner = FakeRunner()
        runner._stream_rc = 0  # /scan: no errors
        result = self._run(runner)
        blob = runner.all_text()
        self.assertIn("chkdsk", blob)
        self.assertIn("/scan", blob)
        self.assertNotIn("/f", blob)          # no destructive step online
        self.assertIn("disk_ok", [n[0] for n in runner.notes])
        self.assertFalse(result["reboot_required"])

    def test_dirty_volume_schedules_offline_fix_with_auto_yes(self):
        runner = FakeRunner()
        runner._stream_rc = 2  # errors found, not fixed online
        result = self._run(runner)
        fixed = [c for c in runner.calls
                 if c[0] == "run" and c[1] == ("chkdsk", "D:", "/f")]
        self.assertEqual(len(fixed), 1)
        self.assertIn("disk_scheduled", [n[0] for n in runner.notes])
        self.assertTrue(result["reboot_required"])

    def test_smart_unavailable_degrades_to_warning(self):
        runner = FakeRunner()
        smart = ("powershell.exe", "-NoProfile", "-ExecutionPolicy",
                 "Bypass", "-Command", disk_repair._PS_SMART)
        runner._outcomes[smart] = (1, "", "cmdlet not found")
        runner._stream_rc = 0
        self._run(runner)
        warns = [n[0] for n in runner.notes if n[2] == "warn"]
        self.assertIn("disk_smart_na", warns)
        self.assertIn("disk_ok", [n[0] for n in runner.notes])

    def test_system_drive_derived_from_systemroot(self):
        with mock.patch.object(disk_repair.platform_info, "systemroot",
                               return_value="E:\\Windows"):
            self.assertEqual(disk_repair.system_drive(), "E:")


class TestGuiWiring(unittest.TestCase):
    """Integration test: FixTool.py imports only repair_core at module
    level (customtkinter is loaded lazily), so we can verify the GUI's
    operation wiring on any OS."""

    @classmethod
    def setUpClass(cls):
        import FixTool  # noqa: F401  (safe: no ctk/tk import at top level)
        cls.fixtool = FixTool

    def test_every_operation_has_translations(self):
        ops = self.fixtool.WindowsRepairApp.OPERATIONS
        self.assertGreaterEqual(len(ops), 5)
        for op_id, (module, start_key, end_key) in ops.items():
            for lang in ("AR", "EN"):
                table = strings_mod.STRINGS[lang]
                self.assertIn(start_key, table,
                              "%s missing %s in %s" % (op_id, start_key, lang))
                self.assertIn(end_key, table,
                              "%s missing %s in %s" % (op_id, end_key, lang))

    def test_operations_reference_real_modules(self):
        import repair_core
        for _op_id, (module, _s, _e) in \
                self.fixtool.WindowsRepairApp.OPERATIONS.items():
            self.assertTrue(
                module.__name__.startswith("repair_core."),
                "operation module outside repair_core: %s" % module.__name__)
            self.assertTrue(hasattr(module, "repair"))


class TestEventLog(unittest.TestCase):
    def test_render_translates_retroactively(self):
        log = eventlog.EventLog(path=os.path.join(tempfile.gettempdir(),
                                                  "fixtool_test.log"))
        log.add("net_winsock")
        log.add(raw="netsh winsock reset")
        ar = log.render(strings_mod.STRINGS["AR"])
        en = log.render(strings_mod.STRINGS["EN"])
        self.assertTrue(any("Winsock" in line for line in ar))
        self.assertTrue(any("Winsock" in line for line in en))
        self.assertTrue(any(line.endswith("netsh winsock reset")
                            for line in en))
        # per-entry timestamps exist and are preserved between renders
        self.assertEqual([l[:22] for l in ar], [l[:22] for l in en])

    def test_save_never_raises_and_writes_file(self):
        path = os.path.join(tempfile.gettempdir(), "fixtool_test2.log")
        log = eventlog.EventLog(path=path)
        log.add("start_msg")
        self.assertTrue(log.save(strings_mod.STRINGS["EN"]))
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("Admin privileges", content)
        os.remove(path)


class TestRunnerInternals(unittest.TestCase):
    def test_fmt_cmd_quotes_arguments_with_spaces(self):
        rendered = fmt_cmd(["reg", "add", "HKLM\\A B", "/v", "x y"])
        self.assertIn('"HKLM\\A B"', rendered)
        self.assertIn('"x y"', rendered)


if __name__ == "__main__":
    unittest.main()

