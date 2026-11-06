"""Unit tests for the repair_core engine.

Runs on ANY OS (Linux CI included): Windows specifics are mocked, so the
repair *decisions* - which command runs, in what order, with what gating -
are verified without touching a real system.

Run:  python -m unittest discover -s tests -v
"""

# Copyright (c) 2026 alm6iri. All rights reserved.
# Use is governed by the Personal and Internal Use License in LICENSE.
# Commercial redistribution, resale, and sublicensing require written permission.

import ast
import os
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repair_core import (
    disk_repair,
    eventlog,
    network_repair,
    platform_info,
    system_repair,
    time_repair,
    update_repair,
)
from repair_core import strings as strings_mod
from repair_core.runner import CmdResult, Runner, fmt_cmd


class FakeRunner:
    """Records every call the repair modules make - no real commands run."""

    def __init__(self, outcomes=None):
        self.calls = []
        self.notes = []
        self.raws = []
        self.timeout_log = []  # (cmd_tuple, timeout) for guard tests
        self._outcomes = outcomes or {}

    def note(self, key, params=(), level="info"):
        self.notes.append((key, tuple(params), level))

    def raw(self, text, level="info"):
        self.raws.append(text)

    def run(self, cmd, timeout=120, report=True, input=None):
        self.calls.append(("run", tuple(cmd)))
        self.timeout_log.append((tuple(cmd), timeout))
        outcome = self._outcomes.get(tuple(cmd))
        if outcome is None:
            outcome = (0, "", "")
        return CmdResult(outcome[0], outcome[1], outcome[2])

    def run_stream(self, cmd, timeout=3600, on_line=None):
        self.calls.append(("run_stream", tuple(cmd)))
        return getattr(self, "_stream_rc", 0)

    def run_bytes(self, cmd, timeout=3600):
        self.calls.append(("run_bytes", tuple(cmd)))
        return 0, b"\xff\xfe" + "did not find any integrity violations".encode(
            "utf-16-le"
        )

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
        self.assertEqual(ar, en, f"missing translations: {ar - en} / {en - ar}")

    def test_render_placeholders(self):
        out = strings_mod.render(
            strings_mod.STRINGS["EN"], "cmd_failed", (5, "sc start x")
        )
        self.assertIn("5", out)
        self.assertIn("sc start x", out)

    def test_cmd_missing_carries_os_reason(self):
        """REGRESSION (v2.2.2): the runner passes (cmd, os_reason) but the
        old template had only {0}, silently swallowing the OS error text."""
        for lang in ("AR", "EN"):
            out = strings_mod.render(
                strings_mod.STRINGS[lang], "cmd_missing", ("wmic", "No such file")
            )
            self.assertIn("wmic", out)
            self.assertIn("No such file", out)

    def test_placeholder_indices_are_contiguous(self):
        """Structural audit: every template's {N} indices must form a
        contiguous 0..max range - a gap like {0},{2} means a param is
        silently never rendered."""
        import re as _re

        for lang, table in strings_mod.STRINGS.items():
            for key, template in table.items():
                indices = sorted({int(m) for m in _re.findall(r"\{(\d+)\}", template)})
                expected = list(range(max(indices) + 1)) if indices else []
                self.assertEqual(
                    indices, expected, f"{lang}/{key} has non-contiguous placeholders"
                )

    def test_placeholder_arity_matches_across_languages(self):
        """The same key must consume the same number of params in AR and
        EN - otherwise one language silently drops (or misses) a value."""
        import re as _re

        def arity(template):
            indices = [int(m) for m in _re.findall(r"\{(\d+)\}", template)]
            return max(indices) + 1 if indices else 0

        for key, ar_template in strings_mod.STRINGS["AR"].items():
            self.assertEqual(
                arity(ar_template),
                arity(strings_mod.STRINGS["EN"][key]),
                f"placeholder arity mismatch for key: {key}",
            )

    def test_every_arity_renders_all_params(self):
        """Rendering each template with its implied arity must surface
        every parameter value (catches format-vs-template drift)."""
        import re as _re

        for lang, table in strings_mod.STRINGS.items():
            for key, template in table.items():
                indices = [int(m) for m in _re.findall(r"\{(\d+)\}", template)]
                if not indices:
                    continue
                count = max(indices) + 1
                params = tuple("<%d>" % i for i in range(count))  # noqa: UP031
                rendered = strings_mod.render(table, key, params)
                for i in range(count):
                    self.assertIn(
                        "<%d>" % i,  # noqa: UP031
                        rendered,
                        "%s/%s dropped param %d" % (lang, key, i),  # noqa: UP031
                    )

    def test_no_dead_localization_keys(self):
        """REVERSE coverage invariant: every key DEFINED in the tables
        must actually be referenced as a quoted literal somewhere in the
        project sources - dead keys accumulate cruft and rot the
        localization tables with zero symptoms. (The forward direction -
        every used key exists - is covered by the static scan test.)"""
        defined = set(strings_mod.STRINGS["AR"])
        sources = []
        core_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "repair_core"
        )
        for name in sorted(os.listdir(core_dir)):
            if name.endswith(".py"):
                sources.append(os.path.join(core_dir, name))
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sources.append(os.path.join(root, "FixTool.py"))
        blob = ""
        for path in sources:
            with open(path, encoding="utf-8") as fh:
                blob += fh.read()
        dead = [
            key
            for key in sorted(defined)
            if (f'"{key}"') not in blob and (f"'{key}'") not in blob
        ]
        self.assertEqual(dead, [], f"dead localization keys: {dead}")

    def test_render_unknown_key_never_crashes(self):
        self.assertEqual(strings_mod.render(strings_mod.STRINGS["EN"], "nope"), "nope")

    def test_every_key_used_in_code_has_translations(self):
        """Static audit: scan the actual sources for every translation key
        passed to Runner.note(...) / EventLog.add(...) and require an AR
        and EN entry for each - a missing translation can never ship."""
        import re

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        used = set()
        core_dir = os.path.join(root, "repair_core")
        for name in os.listdir(core_dir):
            if name.endswith(".py"):
                with open(os.path.join(core_dir, name), encoding="utf-8") as fh:
                    text = fh.read()
                used |= set(re.findall(r'\.note\(\s*"([a-z_0-9]+)"', text))
        gui_path = os.path.join(root, "FixTool.py")
        with open(gui_path, encoding="utf-8") as fh:
            gui = fh.read()
        used |= set(re.findall(r'\.add\(\s*"([a-z_0-9]+)"', gui))
        # verdict keys in system_repair are dynamic; pin them explicitly.
        used |= {"sfc_ok", "sfc_fixed", "sfc_partial", "sfc_unknown"}
        self.assertGreater(len(used), 30)  # sanity: the scan found real keys
        for lang in ("AR", "EN"):
            missing = used - set(strings_mod.STRINGS[lang])
            self.assertEqual(
                missing, set(), f"keys missing {lang} translations: {missing}"
            )


class TestPlatformInfo(unittest.TestCase):
    def test_win10_release_mapping(self):
        self.assertEqual(platform_info.release_from_build(10240, False), "1507")
        self.assertEqual(platform_info.release_from_build(19045, False), "22H2")

    def test_win11_release_mapping(self):
        self.assertEqual(platform_info.release_from_build(22000, True), "21H2")
        self.assertEqual(platform_info.release_from_build(26100, True), "24H2")
        # 25H2 (build 26200) is the current retail Windows 11 release.
        self.assertEqual(platform_info.release_from_build(26200, True), "25H2")

    def test_future_win11_build_is_not_unknown(self):
        # Any build above the newest known one must degrade to a "newer
        # than X" label instead of a scary "Unknown".
        label = platform_info.release_from_build(30000, True)
        self.assertTrue(label.startswith(">"), label)
        self.assertNotIn("Unknown", label)

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

    def test_detect_is_safe_on_any_platform(self):
        """detect() must never raise, and must report availability that
        matches the host it actually runs on (the old assertion hard-coded
        non-Windows behavior, so the suite failed on a real Windows box)."""
        info = platform_info.detect()
        if platform_info.IS_WINDOWS:
            self.assertTrue(info.available)
            self.assertNotIn("non-Windows", info.summary())
        else:
            self.assertFalse(info.available)
            self.assertIn("non-Windows", info.summary())

    def test_info_derived_helpers(self):
        info = platform_info.WindowsInfo()
        info.build, info.ubr = 26200, 1742
        self.assertEqual(info.build_full, "26200.1742")
        info.ubr = 0
        self.assertEqual(info.build_full, "26200")
        info.is_win11 = True
        self.assertEqual(info.major, 11)
        info.is_win11 = False
        self.assertEqual(info.major, 10)

    def test_has_wmic_safe_on_any_host(self):
        # Must always return a bool, never raise; on non-Windows hosts
        # WMIC cannot exist, so the answer is deterministically False.
        result = platform_info.has_wmic()
        self.assertIsInstance(result, bool)
        if not platform_info.IS_WINDOWS:
            self.assertFalse(result)

    def test_for_lang_fallback(self):
        self.assertIs(strings_mod.for_lang("AR"), strings_mod.STRINGS["AR"])
        self.assertIs(strings_mod.for_lang("EN"), strings_mod.STRINGS["EN"])
        # Unknown language codes must fall back to EN, never crash.
        self.assertIs(strings_mod.for_lang("XX"), strings_mod.STRINGS["EN"])


class TestNetworkRepair(unittest.TestCase):
    def test_security_never_touches_local_groups(self):
        """REGRESSION (security): v1 added NetworkService/LocalService to
        the Administrators group - a privilege-escalation misconfiguration.
        This test makes sure it can never come back."""
        runner = FakeRunner()
        with mock.patch.object(network_repair, "service_exists", return_value=True):
            network_repair.repair(runner, None)
        blob = runner.all_text().lower()
        self.assertNotIn("localgroup", blob)
        self.assertNotIn("administrators", blob)

    def test_core_resets_and_adapter_enable_via_powershell(self):
        runner = FakeRunner()
        with mock.patch.object(network_repair, "service_exists", return_value=True):
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
        with mock.patch.object(
            network_repair, "service_exists", side_effect=lambda n: n in existing
        ):
            network_repair.repair(runner, None)
        configured = {c[1] for c in runner.calls if c[0] == "config"}
        self.assertEqual(configured, existing)
        skipped = [n[1][0] for n in runner.notes if n[0] == "service_missing"]
        self.assertIn("CDPSvc", skipped)  # absent on LTSC
        self.assertIn("WlanSvc", skipped)

    def test_appx_skipped_when_package_absent(self):
        runner = FakeRunner()
        probe = (
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            network_repair._PS_APPX_PROBE,
        )
        runner._outcomes[probe] = (0, "none", "")
        with mock.patch.object(network_repair, "service_exists", return_value=True):
            network_repair.repair(runner, None)
        self.assertIn("appx_skip", [n[0] for n in runner.notes])


class TestUpdateRepair(unittest.TestCase):
    def _run(self, runner):
        services = {"wuauserv", "cryptSvc", "bits", "msiserver", "doSvc"}
        with (
            mock.patch.object(
                update_repair, "service_exists", side_effect=lambda n: n in services
            ),
            mock.patch("os.path.isdir", return_value=True),
            mock.patch.object(
                update_repair.platform_info, "systemroot", return_value="X:\\Windows"
            ),
        ):
            return update_repair.repair(runner, None)

    def test_stop_archive_rebuild_flow(self):
        runner = FakeRunner()
        result = self._run(runner)

        stopped = [c[1] for c in runner.calls if c[0] == "stop"]
        self.assertEqual(
            stopped,
            [
                "wuauserv",
                "cryptSvc",
                "bits",
                "msiserver",
                "doSvc",
                # second verified sweep:
                "wuauserv",
                "cryptSvc",
                "bits",
                "msiserver",
                "doSvc",
            ],
        )
        renamed = [c[1] for c in runner.calls if c[0] == "rename"]
        self.assertEqual(
            renamed,
            [
                os.path.join("X:\\Windows", "SoftwareDistribution"),
                os.path.join("X:\\Windows", "System32", "catroot2"),
            ],
        )
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
        self.assertIn("dir_archive_failed", [n[0] for n in runner.notes])

    def test_service_structures_set_consistent(self):
        """INVARIANT: STOP_ORDER, START_ORDER and START_MODES must cover
        the exact same service set - a service added to one structure but
        not the others would be stopped but never restarted (or
        configured but never stopped), breaking the repair symmetry."""
        stop = set(update_repair.STOP_ORDER)
        start = set(update_repair.START_ORDER)
        modes = set(update_repair.START_MODES)
        self.assertGreaterEqual(len(stop), 5)
        self.assertEqual(
            stop, start, "STOP_ORDER vs START_ORDER mismatch: %s" % (stop ^ start)
        )
        self.assertEqual(
            stop, modes, "STOP_ORDER vs START_MODES mismatch: %s" % (stop ^ modes)
        )


class TestTimeRepair(unittest.TestCase):
    def test_peer_list_is_valid(self):
        """REGRESSION: v1 shipped the corrupted peer `://windows.com`."""
        runner = FakeRunner()
        with mock.patch.object(time_repair, "service_exists", return_value=True):
            time_repair.repair(runner, None)
        blob = runner.all_text()
        self.assertNotIn("://windows.com", blob)
        self.assertIn("time.windows.com,0x9", blob)
        self.assertIn("/resync", blob)
        self.assertIn("w32tm", blob)

    def test_start_mode_configured_after_reregister(self):
        """REGRESSION (v2.2.2, guard hardened in round 14): `w32tm
        /unregister` deletes the service registration, wiping any
        earlier `sc config`; the auto start mode must therefore be
        applied AFTER /register or it silently never persists.

        Guard hardening: the original version of this test compared the
        LAST config against the register call, so a mutant that ADDED a
        spurious early config still passed (the late, legitimate config
        kept the assertion green). The guard now asserts that NO config
        call exists before /register at all."""
        runner = FakeRunner()
        with (
            mock.patch.object(time_repair, "service_exists", return_value=True),
            mock.patch.object(time_repair.time, "sleep", lambda s: None),
        ):
            time_repair.repair(runner, None)
        register_idx = None
        config_indices = []
        for i, call in enumerate(runner.calls):
            if call[0] == "run" and call[1][:2] == ("w32tm", "/register"):  # noqa: SIM102
                if register_idx is None:
                    register_idx = i
            if call[0] == "config" and call[1] == "w32time":
                config_indices.append(i)
        self.assertIsNotNone(register_idx)
        self.assertTrue(config_indices, "no w32time start-mode configuration at all")
        early = [i for i in config_indices if i < register_idx]
        self.assertEqual(
            early,
            [],
            f"w32time was configured BEFORE w32tm /register (indices {early}) "
            "- /unregister will wipe it",
        )
        modes = {c[2] for c in runner.calls if c[0] == "config" and c[1] == "w32time"}
        self.assertEqual(modes, {"auto"})

    def test_resync_retries_then_reports_failure(self):
        runner = FakeRunner()
        resync = ("w32tm", "/resync", "/force")
        runner._outcomes[resync] = (1, "", "Access denied")
        with (
            mock.patch.object(time_repair, "service_exists", return_value=True),
            mock.patch.object(time_repair.time, "sleep", lambda s: None),
        ):
            time_repair.repair(runner, None)
        resync_count = sum(1 for c in runner.calls if c[0] == "run" and c[1] == resync)
        self.assertEqual(resync_count, 3)
        self.assertIn(
            "time_resync_failed", [n[0] for n in runner.notes if n[2] == "warn"]
        )


class TestDiskRepair(unittest.TestCase):
    def _run(self, runner):
        with mock.patch.object(
            disk_repair.platform_info, "systemroot", return_value="D:\\Windows"
        ):
            return disk_repair.repair(runner, None)

    def test_healthy_volume_never_schedules_offline_fix(self):
        runner = FakeRunner()
        runner._stream_rc = 0  # /scan: no errors
        result = self._run(runner)
        blob = runner.all_text()
        self.assertIn("chkdsk", blob)
        self.assertIn("/scan", blob)
        self.assertNotIn("/f", blob)  # no destructive step online
        self.assertIn("disk_ok", [n[0] for n in runner.notes])
        self.assertFalse(result["reboot_required"])

    def test_dirty_volume_schedules_offline_fix_with_auto_yes(self):
        runner = FakeRunner()
        runner._stream_rc = 2  # errors found, not fixed online
        result = self._run(runner)
        fixed = [
            c for c in runner.calls if c[0] == "run" and c[1] == ("chkdsk", "D:", "/f")
        ]
        self.assertEqual(len(fixed), 1)
        self.assertIn("disk_scheduled", [n[0] for n in runner.notes])
        self.assertTrue(result["reboot_required"])

    def test_smart_unavailable_degrades_to_warning(self):
        runner = FakeRunner()
        smart = (
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            disk_repair._PS_SMART,
        )
        runner._outcomes[smart] = (1, "", "cmdlet not found")
        runner._stream_rc = 0
        self._run(runner)
        warns = [n[0] for n in runner.notes if n[2] == "warn"]
        self.assertIn("disk_smart_na", warns)
        self.assertIn("disk_ok", [n[0] for n in runner.notes])

    def test_system_drive_derived_from_systemroot(self):
        with mock.patch.object(
            disk_repair.platform_info, "systemroot", return_value="E:\\Windows"
        ):
            self.assertEqual(disk_repair.system_drive(), "E:")

    def test_offline_fix_never_killed_midrepair(self):
        """DATA-INTEGRITY GUARD (mutation-validated): the scheduled
        chkdsk /f call must carry a LONG timeout (>= 3600s). A live
        filesystem repair that gets killed mid-fix (a 120s timeout
        would) risks volume corruption - this pins the v2.2.2 fix."""
        runner = FakeRunner()
        runner._stream_rc = 2  # dirty volume -> /f scheduled
        with mock.patch.object(
            disk_repair.platform_info, "systemroot", return_value="D:\\Windows"
        ):
            disk_repair.repair(runner, None)
        fixes = [
            timeout
            for cmd, timeout in runner.timeout_log
            if cmd == ("chkdsk", "D:", "/f")
        ]
        self.assertEqual(len(fixes), 1)
        self.assertGreaterEqual(
            fixes[0],
            3600,
            f"chkdsk /f timeout {fixes[0]}s can kill a live filesystem repair",
        )


class TestGuiWiring(unittest.TestCase):
    """Integration test: FixTool.py imports only repair_core at module
    level (customtkinter is loaded lazily), so we can verify the GUI's
    operation wiring on any OS."""

    @classmethod
    def setUpClass(cls):
        import FixTool

        cls.fixtool = FixTool

    def test_every_operation_has_translations(self):
        ops = self.fixtool.WindowsRepairApp.OPERATIONS
        self.assertGreaterEqual(len(ops), 5)
        for op_id, (module, start_key, end_key) in ops.items():
            for lang in ("AR", "EN"):
                table = strings_mod.STRINGS[lang]
                self.assertIn(
                    start_key, table, f"{op_id} missing {start_key} in {lang}"
                )
                self.assertIn(end_key, table, f"{op_id} missing {end_key} in {lang}")

    def test_operations_reference_real_modules(self):
        for module, _s, _e in self.fixtool.WindowsRepairApp.OPERATIONS.values():
            self.assertTrue(
                module.__name__.startswith("repair_core."),
                f"operation module outside repair_core: {module.__name__}",
            )
            self.assertTrue(hasattr(module, "repair"))


class TestReleaseHygiene(unittest.TestCase):
    """Release-integrity invariants: version consistency across every
    artifact and presence of all release assets."""

    def test_version_consistency_across_project(self):
        from repair_core import __version__

        # SemVer-shaped single source of truth.
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # The Win32 manifest must carry the same version (x.0 suffix).
        with open(
            os.path.join(root, "packaging", "app.manifest"), encoding="utf-8"
        ) as fh:
            manifest = fh.read()
        self.assertIn(f'version="{__version__}.0"', manifest)

    def test_release_assets_present(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for rel in (
            "FixTool.py",
            "app_icon.ico",
            "Windows-LTSC-Repair.spec",
            "packaging/app.manifest",
            "packaging/build_windows.bat",
            "requirements.txt",
            "README.md",
        ):
            self.assertTrue(
                os.path.isfile(os.path.join(root, rel)), f"missing release asset: {rel}"
            )

    def test_spec_pins_icon_and_uac(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(
            os.path.join(root, "Windows-LTSC-Repair.spec"), encoding="utf-8"
        ) as fh:
            spec = fh.read()
        self.assertIn("uac_admin=True", spec)
        self.assertIn("console=False", spec)
        self.assertIn("app_icon.ico", spec)
        self.assertIn("collect_data_files", spec)

    def test_manifest_dpi_matches_runtime_choice(self):
        """The standalone manifest must declare SYSTEM dpi-aware, matching
        the app's documented runtime choice (Tk 8.6 cannot handle
        WM_DPICHANGED; PMv2 would leave windows unscaled)."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(
            os.path.join(root, "packaging", "app.manifest"), encoding="utf-8"
        ) as fh:
            manifest = fh.read()
        self.assertIn("<dpiAware", manifest)
        self.assertIn("true</dpiAware>", manifest)
        self.assertNotIn("PerMonitorV2", manifest)

    def test_executable_name_consistent_across_release_assets(self):
        """The product EXE name must be identical in the PyInstaller spec
        (name=), the build script (dist check) and the README (documented
        output) - a rename in one asset but not the others would ship a
        broken or misdocumented release silently."""
        exe = "Windows-LTSC-Repair"
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(
            os.path.join(root, "Windows-LTSC-Repair.spec"), encoding="utf-8"
        ) as fh:
            spec = fh.read()
        self.assertIn(f'name="{exe}"', spec)
        with open(
            os.path.join(root, "packaging", "build_windows.bat"),
            encoding="utf-8",
            errors="replace",
        ) as fh:
            bat = fh.read()
        self.assertIn(f"dist\\{exe}.exe", bat)
        with open(os.path.join(root, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        self.assertIn(f"dist\\{exe}.exe", readme)


class TestEndToEndIntegration(unittest.TestCase):
    """The full-pipeline E2E contract that was previously verified only
    by manual smoke scripts: every repair module runs through the REAL
    Runner event pipeline (note/raw/fmt_cmd) into a REAL EventLog, with
    no real commands executed. Guards the module -> runner -> eventlog
    -> strings flow end to end, on any OS."""

    def _pipeline_runner(self, log, stream_rc=0):
        class PipelineRunner(Runner):
            def run(self, cmd, timeout=120, report=True, input=None):
                if report:
                    self._raw(fmt_cmd(cmd), "cmd")
                return CmdResult(0, "none", "")

            def run_stream(self, cmd, timeout=3600, on_line=None):
                self._raw(fmt_cmd(cmd), "cmd")
                return stream_rc

            def run_bytes(self, cmd, timeout=3600):
                self._raw(fmt_cmd(cmd), "cmd")
                return 0, ("did not find any integrity violations".encode("utf-16-le"))

            def stop_service(self, name, timeout=30):
                return True

            def start_service(self, name, wait=15, retries=1):
                return True

            def set_start_mode(self, name, mode):
                return True

            def rename_dir(self, path, suffix=".bak"):
                return path + ".bak_E2E"

            def delete_path(self, path):
                return True

            def cleanup_backups(self, path, suffix=".bak"):
                return 0

        return PipelineRunner(log.add)

    SCENARIOS = [  # noqa: RUF012
        # (tag, module, stream exit code, expected reboot_required)
        # The stream code maps to chkdsk /scan for disk scenarios and to
        # DISM for the system-files scenario; SFC output is fed as real
        # UTF-16LE bytes through run_bytes.
        ("net", network_repair, 0, True),  # winsock/ip resets
        ("upd", update_repair, 0, False),
        ("time", time_repair, 0, False),
        ("sys", system_repair, 0, False),  # SFC verdict: no violations
        ("disk-healthy", disk_repair, 0, False),
        ("disk-dirty", disk_repair, 2, True),  # chkdsk /f scheduled
    ]

    def _run_all(self, log):
        from contextlib import ExitStack

        with ExitStack() as stack:
            for module in (network_repair, update_repair, time_repair):
                stack.enter_context(
                    mock.patch.object(module, "service_exists", return_value=True)
                )
            stack.enter_context(mock.patch("os.path.isdir", return_value=True))
            stack.enter_context(
                mock.patch.object(
                    platform_info, "systemroot", return_value="C:\\Windows"
                )
            )
            results = {}
            for tag, module, scan_rc, _expected in self.SCENARIOS:
                runner = self._pipeline_runner(log, stream_rc=scan_rc)
                results[tag] = module.repair(runner, None)
            return results

    def test_six_scenarios_flags_and_security(self):
        log = eventlog.EventLog(
            path=os.path.join(tempfile.gettempdir(), "fixtool_e2e.log")
        )
        log.add("start_msg")
        results = self._run_all(log)
        for tag, _module, _rc, expected in self.SCENARIOS:
            self.assertEqual(
                results[tag].get("reboot_required"),
                expected,
                f"wrong reboot_required for scenario {tag}: {results[tag]}",
            )
        # Security invariants over the FULL rendered pipeline output.
        blob = " ".join(log.render(strings_mod.STRINGS["EN"])).lower()
        self.assertNotIn("localgroup", blob)
        self.assertNotIn("administrators", blob)
        self.assertNotIn("://windows.com", blob)
        # Key artifacts of every module flowed through the pipeline.
        self.assertIn("enable-netadapter", blob)  # network (WMIC-free)
        self.assertIn("softwaredistribution.bak_e2e", blob)  # archived, not deleted
        self.assertIn("time.windows.com,0x9", blob)  # valid NTP peer
        self.assertIn("dism", blob)  # component store
        self.assertIn("chkdsk", blob)  # disk health
        self.assertGreater(len(log.entries), 40)

    def test_log_dual_language_render_and_save(self):
        log = eventlog.EventLog(
            path=os.path.join(tempfile.gettempdir(), "fixtool_e2e_i18n.log")
        )
        log.add("start_msg")
        self._run_all(log)
        ar = " ".join(log.render(strings_mod.STRINGS["AR"]))
        en = " ".join(log.render(strings_mod.STRINGS["EN"]))
        # Arabic surface renders real Arabic text (not raw keys).
        self.assertIn("تصفير", ar)  # net_winsock
        self.assertIn("جدولة", ar)  # disk_scheduled (dirty)
        self.assertNotIn("net_winsock", ar)  # no raw keys leaked
        self.assertIn("Winsock", en)
        self.assertIn("scheduled", en)
        # The disk-mirror writes cleanly and mirrors both tables.
        self.assertTrue(log.save(strings_mod.STRINGS["AR"]))
        with open(log.path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("تصفير", content)
        os.remove(log.path)


# ---------------------------------------------------------------------------
# Headless GUI harness: a recording mock of customtkinter that lets the
# REAL WindowsRepairApp logic (busy-lock races, RTL/LTR mirroring, the
# main-thread pump) be tested without any display or Tk installation.
# ---------------------------------------------------------------------------
class _MockWidget:
    """Recording stand-in for any CustomTkinter widget."""

    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = dict(kwargs)
        self.command = kwargs.get("command")
        self.configures = []
        self.packs = []
        self.grids = []
        self.forgotten = 0
        self.destroyed = 0

    def configure(self, **kwargs):
        self.configures.append(kwargs)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def pack(self, **kwargs):
        self.packs.append(kwargs)

    def pack_forget(self):
        self.forgotten += 1

    def grid(self, **kwargs):
        self.grids.append(kwargs)

    def destroy(self):
        self.destroyed += 1

    def pack_propagate(self, _flag):
        pass

    def tag_config(self, *_args, **_kwargs):
        pass

    def insert(self, *_a, **_k):
        pass

    def delete(self, *_a, **_k):
        pass

    def see(self, *_a):
        pass

    def attributes(self, *_args, **_kwargs):
        pass

    def grab_set(self):
        pass

    def resizable(self, *_a):
        pass

    def geometry(self, _value):
        pass

    def title(self, text=None):
        if not hasattr(self, "titles"):
            self.titles = []
        if text is not None:
            self.titles.append(text)
        return self.titles[-1] if self.titles else ""


class _MockCtkRoot(_MockWidget):
    """Recording stand-in for ctk.CTk()."""

    def __init__(self):
        super().__init__()
        self.titles = []
        self.after_calls = []
        self.iconbitmap_calls = []

    def title(self, text=None):
        if text is not None:
            self.titles.append(text)
        return self.titles[-1] if self.titles else ""

    def iconbitmap(self, path):
        self.iconbitmap_calls.append(path)

    def after(self, ms, callback):
        self.after_calls.append((ms, callback))

    def mainloop(self):
        pass


class _MockToplevel(_MockWidget):
    all_instances = []  # noqa: RUF012

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        _MockToplevel.all_instances.append(self)


def _make_mock_ctk():
    import types

    module = types.ModuleType("mock_customtkinter")
    module.set_appearance_mode = lambda *a, **k: None
    module.set_default_color_theme = lambda *a, **k: None
    module.CTk = _MockCtkRoot
    module.CTkLabel = _MockWidget
    module.CTkButton = _MockWidget
    module.CTkFrame = _MockWidget
    module.CTkTextbox = _MockWidget
    module.CTkToplevel = _MockToplevel
    module.CTkFont = lambda **kwargs: kwargs
    return module


class TestGuiAppLogic(unittest.TestCase):
    """The REAL WindowsRepairApp logic, exercised headless through the
    recording customtkinter mock - the GUI layer was the last untested
    part of the project."""

    def _make_app(self):
        import FixTool

        _MockToplevel.all_instances = []
        log_path = os.path.join(tempfile.gettempdir(), "fixtool_gui_headless.log")
        with mock.patch.object(eventlog, "default_log_path", return_value=log_path):
            app = FixTool.WindowsRepairApp(_make_mock_ctk())
        return app, log_path

    def test_operation_dispatch_is_race_free(self):
        """Clicking a second operation while one is in flight must be a
        no-op (busy lock), and the buttons must re-enable only after the
        main-thread pump consumed the completion flag."""
        import time as _t

        app, log_path = self._make_app()
        try:
            released = threading.Event()

            def slow_repair(_runner, _info):
                released.wait(10)
                return {"reboot_required": False}

            with mock.patch.object(network_repair, "repair", slow_repair):
                app.btn_net.command()  # starts the (blocked) worker
                app.btn_upd.command()  # must be IGNORED while busy
                keys = [e["key"] for e in app.log.entries]
                self.assertIn("net_start", keys)
                self.assertNotIn("upd_start", keys)
                self.assertEqual(app.btn_net.configures[-1].get("state"), "disabled")
                released.set()
                deadline = _t.monotonic() + 5
                while _t.monotonic() < deadline:
                    app._poll_log()
                    if (
                        not getattr(app, "_pending_busy_off", False)
                        and app.btn_net.configures
                        and app.btn_net.configures[-1].get("state") == "normal"
                    ):
                        break
                    _t.sleep(0.02)
                self.assertEqual(app.btn_net.configures[-1].get("state"), "normal")
                # Once idle, the second operation is accepted.
                with mock.patch.object(update_repair, "repair", lambda r, i: {}):
                    app.btn_upd.command()
                    keys = [e["key"] for e in app.log.entries]
                    self.assertIn("upd_start", keys)
                    self.assertIn("net_end", keys)
        finally:
            if os.path.exists(log_path):
                os.remove(log_path)

    def test_language_toggle_mirrors_layout(self):
        """AR -> EN must flip every anchor/side AND re-pack the log
        caption (pack options are immutable via configure - the v2.2.3
        mirroring fix)."""
        app, log_path = self._make_app()
        try:
            self.assertEqual(app.log_label.packs[0].get("anchor"), "e")
            app.btn_lang.command()  # AR -> EN
            self.assertGreaterEqual(app.log_label.forgotten, 1)
            self.assertEqual(app.log_label.packs[-1].get("anchor"), "w")
            self.assertEqual(app.status_label.configures[-1].get("anchor"), "w")
            self.assertIn("Ready", app.status_label.configures[-1].get("text", ""))
            self.assertEqual(app.button_frame.packs[-1].get("side"), "left")
            self.assertEqual(app.log_frame.packs[-1].get("side"), "right")
            from repair_core import __version__ as core_version

            self.assertTrue(app.root.titles[-1].endswith(core_version))
        finally:
            os.remove(log_path)

    def test_busy_state_disables_all_buttons_including_reboot(self):
        app, log_path = self._make_app()
        try:
            app._set_busy(True)
            for btn in app._action_buttons + [app.btn_reboot]:
                self.assertEqual(btn.configures[-1].get("state"), "disabled")
            app._set_busy(False)
            for btn in app._action_buttons + [app.btn_reboot]:
                self.assertEqual(btn.configures[-1].get("state"), "normal")
        finally:
            os.remove(log_path)

    def test_reboot_dialog_blocked_while_busy(self):
        app, log_path = self._make_app()
        try:
            app._busy_lock.acquire()
            try:
                app.btn_reboot.command()  # must silently do nothing
                self.assertEqual(_MockToplevel.all_instances, [])
            finally:
                app._busy_lock.release()
            app.btn_reboot.command()  # idle -> dialog is created
            self.assertEqual(len(_MockToplevel.all_instances), 1)
        finally:
            os.remove(log_path)

    def test_poll_log_survives_widget_failure(self):
        """One broken render cycle must never kill the pump (the pump
        reschedules itself even when the widget layer explodes)."""
        app, log_path = self._make_app()
        try:
            before = len(app.root.after_calls)

            def boom(*_a, **_k):
                raise RuntimeError("widget exploded")

            with mock.patch.object(app.log_text, "delete", boom):
                app._poll_log()  # must not raise
            self.assertGreater(len(app.root.after_calls), before)
        finally:
            os.remove(log_path)


class TestBootHelpers(unittest.TestCase):
    """Degradation contracts for the FixTool boot layer - the UAC /
    elevation / DPI path, which is the most safety-critical boot code in
    the app and previously had zero automated coverage.

    Interactive-behavior tests are SKIPPED ON WINDOWS on purpose: a
    naive test would pop REAL UAC prompts and message boxes during the
    test-gated release build. The skip markers are the guard."""

    @classmethod
    def setUpClass(cls):
        import FixTool

        cls.fixtool = FixTool

    def test_is_admin_returns_bool(self):
        # Contract on BOTH platforms: a bool, never an exception.
        result = self.fixtool._is_admin()
        self.assertIsInstance(result, bool)
        if os.name != "nt":
            self.assertFalse(result)  # deterministic off-Windows

    def test_enable_dpi_awareness_never_raises(self):
        # Contract on BOTH platforms: best-effort, always silent.
        self.fixtool._enable_dpi_awareness()

    @unittest.skipIf(os.name == "nt", "would show a real message box")
    def test_message_box_is_silent_noop_off_windows(self):
        # Off-Windows there is no user32: must degrade to a silent no-op.
        self.fixtool._message_box("text", "caption")

    @unittest.skipIf(os.name == "nt", "would trigger a real UAC prompt")
    def test_relaunch_elevated_degrades_to_zero_off_windows(self):
        # No windll off-Windows: must degrade to the failure code (<= 32)
        # without raising.
        ret = self.fixtool._relaunch_elevated()
        self.assertIsInstance(ret, int)
        self.assertLessEqual(ret, 32)

    @unittest.skipIf(os.name == "nt", "depends on the host's GUI install")
    def test_try_load_gui_degrades_to_none_off_windows(self):
        # customtkinter cannot be installed here: must return None
        # (and the missing-library dialog degrades silently off-Windows).
        self.assertIsNone(self.fixtool._try_load_gui())

    @unittest.skipIf(os.name == "nt", "main() would launch the real GUI")
    def test_main_platform_guard_off_windows(self):
        import io
        from contextlib import redirect_stderr

        buf = io.StringIO()
        with redirect_stderr(buf):
            code = self.fixtool.main()
        self.assertEqual(code, 1)
        # The guard message is localized (AR default UI language).
        self.assertIn("Windows 10/11", buf.getvalue())


class TestEventLog(unittest.TestCase):
    def test_render_translates_retroactively(self):
        log = eventlog.EventLog(
            path=os.path.join(tempfile.gettempdir(), "fixtool_test.log")
        )
        log.add("net_winsock")
        log.add(raw="netsh winsock reset")
        ar = log.render(strings_mod.STRINGS["AR"])
        en = log.render(strings_mod.STRINGS["EN"])
        self.assertTrue(any("Winsock" in line for line in ar))
        self.assertTrue(any("Winsock" in line for line in en))
        self.assertTrue(any(line.endswith("netsh winsock reset") for line in en))
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

    def test_default_log_path_falls_back_safely(self):
        """The log location must always resolve inside the user profile,
        preferring Desktop and degrading to the profile root when the
        Desktop is missing or redirected (e.g. OneDrive)."""
        import os as _os

        path = eventlog.default_log_path()
        self.assertTrue(path.endswith("Fixer_Events_Log.txt"))
        home = _os.path.expanduser("~")
        self.assertTrue(
            _os.path.abspath(path).startswith(_os.path.abspath(home)),
            f"log escaped the user profile: {path}",
        )
        # When the Desktop folder exists, it must be the preferred target.
        desktop = os.path.join(home, "Desktop")
        if os.path.isdir(desktop):
            self.assertEqual(
                os.path.dirname(os.path.abspath(path)), os.path.abspath(desktop)
            )

    def test_concurrent_appends_and_renders_thread_safe(self):
        """THREAD-SAFETY CONTRACT (documented, now tested): worker
        threads only append (list.append is atomic under the GIL) while
        the main thread renders - no exceptions, no lost or corrupted
        entries. This is the exact access pattern the GUI pump uses."""
        log = eventlog.EventLog(
            path=os.path.join(tempfile.gettempdir(), "fixtool_conc.log")
        )
        log.add("start_msg")
        errors = []
        start = threading.Event()  # barrier: render loop is armed first

        def appender(tag):
            try:
                start.wait()  # hold until the main thread is ready
                for i in range(250):
                    log.add("net_winsock")
                    log.add(raw="line-%s-%d" % (tag, i))  # noqa: UP031
            except Exception as exc:  # pragma: no cover - failure path  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=appender, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        renders = 0
        try:
            # do-while shape: render at least once AND keep rendering
            # while the appenders are alive (true concurrent access).
            while True:
                log.render(strings_mod.STRINGS["EN"])
                renders += 1
                if not any(t.is_alive() for t in threads):
                    break
                if renders == 1:
                    start.set()  # release the appenders mid-rendering
        except Exception as exc:  # pragma: no cover - failure path  # noqa: BLE001
            errors.append(exc)
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertGreater(renders, 0)
        # Every single append survived: 4 threads x 500 entries + 1.
        self.assertEqual(len(log.entries), 2001)
        # The rendered output is complete and well-formed.
        lines = log.render(strings_mod.STRINGS["EN"])
        self.assertEqual(len(lines), 2001)
        self.assertTrue(all(line.startswith("[") for line in lines))


class TestRunnerInternals(unittest.TestCase):
    def test_fmt_cmd_quotes_arguments_with_spaces(self):
        rendered = fmt_cmd(["reg", "add", "HKLM\\A B", "/v", "x y"])
        self.assertIn('"HKLM\\A B"', rendered)
        self.assertIn('"x y"', rendered)


class TestRunnerHardening(unittest.TestCase):
    """Regression tests for the v2.2 audit fixes - runnable on any OS."""

    def _runner(self):
        events = []
        return Runner(on_event=lambda k, p, r, l: events.append((k, p, r, l))), events

    def test_service_state_fallback_parses_sc_output(self):
        """The sc-parse fallback must still work (English hosts / tests)."""
        runner, _ = self._runner()
        sample = (
            "SERVICE_NAME: wuauserv\r\n"
            "        TYPE               : 20  WIN32_SHARE_PROCESS\r\n"
            "        STATE              : 4  RUNNING \r\n"
            "                                (STOPPABLE,NOT_PAUSABLE)\r\n"
        )
        # Force the fallback: on a real Windows host the SCM API answers
        # first, so the parser would never be exercised without this patch.
        with (
            mock.patch.object(runner, "run", return_value=CmdResult(0, sample, "")),
            mock.patch("repair_core.runner._native_service_state", return_value=None),
        ):
            self.assertEqual(runner.service_state("wuauserv"), "RUNNING")

    def test_native_service_state_never_raises(self):
        """Contract test (runs on Windows hosts AND CI): the SCM probe
        either returns a canonical state name or None - it must never
        raise, whatever the service or platform."""
        from repair_core import runner as runner_mod

        state = runner_mod._native_service_state("wuauserv")
        valid = set(runner_mod._SERVICE_STATE_NAMES.values()) | {None}
        self.assertIn(state, valid)
        # A non-existent service must map to None on every platform.
        self.assertIsNone(runner_mod._native_service_state("DefinitelyNotAService123"))

    def test_run_stream_hard_deadline_kills_stalled_process(self):
        """A process that never exits must be killed at the deadline,
        not hang the worker thread forever.

        Uses sys.executable (NOT `sleep`/`echo`): POSIX binaries don't
        exist on Windows, and this suite gates the Windows release build
        - every command here must run identically on BOTH platforms."""
        import time as _t

        runner, events = self._runner()
        stall = [sys.executable, "-c", "import time; time.sleep(30)"]
        started = _t.monotonic()
        rc = runner.run_stream(stall, timeout=1)
        elapsed = _t.monotonic() - started
        self.assertIsNone(rc)
        self.assertLess(elapsed, 10)  # killed ~1s, not 30s
        self.assertIn("cmd_timeout", [e[0] for e in events if e[0]])

    def test_run_stream_streams_lines_and_returns_rc(self):
        runner, _events = self._runner()
        seen = []
        hello = [sys.executable, "-c", "print('hello-audit')"]
        rc = runner.run_stream(hello, timeout=30, on_line=seen.append)
        self.assertEqual(rc, 0)
        self.assertIn("hello-audit", seen)

    def test_run_stream_propagates_nonzero_exit_code(self):
        """GUARD (added in round 14): run_stream must faithfully
        propagate a NON-ZERO exit code. The previous guards only pinned
        the timeout path (None) and the success path (0) - a mutant
        swallowing every exit code into 0 survived the whole suite."""
        runner, _events = self._runner()
        fail = [sys.executable, "-c", "import sys; sys.exit(3)"]
        rc = runner.run_stream(fail, timeout=30)
        self.assertEqual(rc, 3)

    def test_rename_dir_survives_same_second_collision(self):
        """Two archives in the same second must not be misreported as a
        locked directory."""
        import tempfile as _tf

        base = _tf.mkdtemp(prefix="fixtool_coll_")
        try:
            source = os.path.join(base, "src")
            os.makedirs(source)
            with mock.patch(
                "repair_core.runner.time.strftime", return_value="20260101_000000"
            ):
                first = self._plain_rename(source)
                os.makedirs(source)  # recreate for 2nd archive
                second = self._plain_rename(source)
            self.assertNotEqual(first, second)
            self.assertTrue(second.endswith("_1"))
            self.assertTrue(os.path.isdir(second))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_cleanup_backups_reports_locked_backup(self):
        """REGRESSION (v2.2.2): a locked old backup used to be skipped
        silently; it must now emit a warning so the operator knows."""
        import tempfile as _tf

        events = []
        runner = Runner(on_event=lambda k, p, r, l: events.append((k, p, l)))
        base = _tf.mkdtemp(prefix="fixtool_bak_")
        try:
            live = os.path.join(base, "dir")
            os.makedirs(live)
            locked = live + ".bak_20260101_000000"
            with open(locked, "w", encoding="utf-8") as fh:
                fh.write("old backup")
            with mock.patch.object(Runner, "delete_path", return_value=False):
                removed = runner.cleanup_backups(live)
            self.assertEqual(removed, 0)
            warns = [
                e for e in events if e[0] == "backup_delete_failed" and e[2] == "warn"
            ]
            self.assertEqual(len(warns), 1)
            self.assertIn("20260101", warns[0][1][0])
        finally:
            shutil.rmtree(base, ignore_errors=True)

    @staticmethod
    def _plain_rename(path):
        from repair_core.runner import Runner

        runner = Runner(on_event=lambda *a: None)
        return runner.rename_dir(path)


class TestSfcDecoding(unittest.TestCase):
    """Regression tests for the SFC output decoder (v2.2 rewrite)."""

    def test_utf16le_ascii_roundtrip(self):
        from repair_core.system_repair import _decode_sfc

        msg = "Windows Resource Protection did not find any integrity violations."
        self.assertEqual(_decode_sfc(msg.encode("utf-16-le")), msg)

    def test_utf16le_mixed_cjk_roundtrip(self):
        """Chinese-Windows SFC output (CJK text + ASCII paths) must be
        detected via NUL-parity evidence, not rejected as mojibake."""
        from repair_core.system_repair import _decode_sfc

        msg = "Windows 资源保护找到了损坏文件 C:\\Windows\\system32\\dll 100%"
        decoded = _decode_sfc(msg.encode("utf-16-le"))
        self.assertIn("Windows", decoded)
        self.assertIn("system32", decoded)

    def test_legacy_codepage_not_misdecoded_as_utf16(self):
        from repair_core.system_repair import _decode_sfc

        msg = "Repairs complete: cafe files."
        decoded = _decode_sfc(msg.encode("cp850"))
        self.assertIn("Repairs complete", decoded)

    def test_empty_input(self):
        from repair_core.system_repair import _decode_sfc

        self.assertEqual(_decode_sfc(b""), "")

    def test_mojibake_detector(self):
        from repair_core.system_repair import _looks_like_mojibake

        self.assertFalse(_looks_like_mojibake("plain ascii text"))
        self.assertTrue(
            _looks_like_mojibake("".join(chr(0x4E00 + i % 100) for i in range(100)))
        )


class TestSourceIntegrity(unittest.TestCase):
    """Guards against SILENT shadowing hazards that Python permits:
    duplicate dict keys and duplicate method names both override their
    predecessors without any error, so a future edit could silently
    disable a translation or a test. These invariants make that
    impossible to reintroduce."""

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @staticmethod
    def _parse(path):
        import ast

        with open(path, encoding="utf-8") as fh:
            return ast.parse(fh.read())

    def test_no_duplicate_string_keys(self):
        """A duplicated key in a strings dict literal silently overrides
        the earlier entry - the AR or EN table would lose a translation
        with zero symptoms."""
        tree = self._parse(os.path.join(self.ROOT, "repair_core", "strings.py"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                seen = set()
                for key in node.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        self.assertNotIn(
                            key.value,
                            seen,
                            f"duplicate key shadows an earlier entry: {key.value}",
                        )
                        seen.add(key.value)

    def test_no_duplicate_test_methods(self):
        """A duplicated test method name silently shadows the earlier
        test - the suite count would drop with zero symptoms."""
        path = os.path.abspath(__file__)
        tree = self._parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                seen = set()
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        self.assertNotIn(
                            item.name,
                            seen,
                            "duplicate method shadows an earlier test: "
                            f"{node.name}.{item.name}",
                        )
                        seen.add(item.name)

    def test_no_duplicate_module_level_classes(self):
        """Duplicate module-level class names silently shadow each other
        (the same Python hazard as duplicate dict keys) - a whole test
        class or core class could disappear without any error."""
        root = self.ROOT
        targets = [
            os.path.join(root, "FixTool.py"),
            os.path.join(root, "tests", "test_core.py"),
        ]
        core_dir = os.path.join(root, "repair_core")
        for name in sorted(os.listdir(core_dir)):
            if name.endswith(".py"):
                targets.append(os.path.join(core_dir, name))
        for path in targets:
            tree = self._parse(path)
            seen = set()
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    self.assertNotIn(
                        node.name,
                        seen,
                        "duplicate class shadows an earlier definition "
                        f"in {path}: {node.name}",
                    )
                    seen.add(node.name)

    def test_readme_test_count_is_accurate(self):
        """The README's stated test count must equal the number of test
        methods actually defined - documentation can never drift from
        reality."""
        tree = self._parse(os.path.abspath(__file__))
        count = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        )
        with open(os.path.join(self.ROOT, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        self.assertIn(
            f"{count} unit tests",
            readme,
            "README claims a stale test count (actual: %d)" % count,  # noqa: UP031
        )

    def test_no_unused_imports(self):
        """Dead imports are latent bugs: they hide missing functionality,
        confuse packagers and rot the module graph. Every import in the
        project must be referenced somewhere in its file (beyond the
        import statement itself)."""
        import re

        targets = [os.path.join(self.ROOT, "FixTool.py"), os.path.abspath(__file__)]
        core_dir = os.path.join(self.ROOT, "repair_core")
        for name in sorted(os.listdir(core_dir)):
            if name.endswith(".py"):
                targets.append(os.path.join(core_dir, name))
        for path in targets:
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            tree = ast.parse(src)
            imported = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported.append(alias.asname or alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name != "*":
                            imported.append(alias.asname or alias.name)
            body = re.sub(r"^import .*$", "", src, flags=re.MULTILINE)
            body = re.sub(r"^from .*? import .*$", "", body, flags=re.MULTILINE)
            for name in imported:
                self.assertTrue(
                    re.search(rf"\b{re.escape(name)}\b", body),
                    f"{path} imports '{name}' but never uses it",
                )

    def test_package_all_matches_actual_modules(self):
        """repair_core.__all__ must list exactly the package's real
        modules - a drift (module added but not exported, or stale
        entry) breaks star-imports and misdocuments the API."""
        import repair_core

        core_dir = os.path.join(self.ROOT, "repair_core")
        actual = {
            name[:-3]
            for name in os.listdir(core_dir)
            if name.endswith(".py") and name != "__init__.py"
        }
        listed = set(repair_core.__all__)
        self.assertEqual(
            listed,
            actual,
            f"__all__ drift - missing: {actual - listed} / stale: {listed - actual}",
        )


if __name__ == "__main__":
    unittest.main()
