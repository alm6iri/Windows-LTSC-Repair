# Windows Repair Tool 🛠️ (LTSC + all Windows 10/11 editions)

An enterprise-grade GUI utility, written natively in **Python** with
**CustomTkinter**, that diagnoses and repairs deep operating-system
failures on **every edition of Windows 10 and Windows 11** — Home, Pro,
Pro for Workstations, Enterprise, Education, **all LTSC releases
(2015/2016/2019/2021/2024)**, IoT Enterprise (incl. IoT LTSC) — from
build 1507 all the way to 24H2/LTSC 2024.

## Supported compatibility matrix 🧩

| | Windows 10 (1507 → 22H2 / LTSC 2021) | Windows 11 (21H2 → 24H2 / LTSC 2024) |
|---|---|---|
| Network repair | ✅ `wmic` fallback available | ✅ PowerShell `Enable-NetAdapter` (WMIC removed in 24H2) |
| Update reset | ✅ incl. `doSvc` (Delivery Optimization) | ✅ |
| Time sync | ✅ | ✅ |
| SFC + DISM repair | ✅ | ✅ (handles SFC's UTF-16 redirected output) |
| Disk health (CHKDSK + SMART) | ✅ online `/scan`, offline fix scheduled on reboot | ✅ |
| AppX re-register | ✅ auto-skipped on Store-less images (LTSC) | ✅ |

## Architecture 🧠

The tool is split into a unit-testable core and a thin GUI:

```
FixTool.py                  # GUI (CustomTkinter) + UAC elevation + DPI awareness
repair_core/
  platform_info.py          # SKU/build/LTSC/IoT detection (registry-driven, zero subprocesses)
  runner.py                 # Console-free command runner: timeouts, retries, verified service stops
  network_repair.py         # Winsock/IP reset, adapter re-enable, service gating, AppX probe
  update_repair.py          # Verified service stops, ARCHIVE (rename) instead of rd /s /q, restart chain
  time_repair.py            # w32time re-register, valid NTP peers, resync retries
  system_repair.py          # DISM /RestoreHealth + sfc /scannow (UTF-16-safe)
  disk_repair.py            # SMART health + online chkdsk /scan; offline fix scheduled only when needed
  strings.py                # Full AR/EN localization (symmetric, test-enforced)
  eventlog.py               # Thread-safe event log + desktop log file
tests/test_core.py          # 49 unit tests - run on ANY OS (Windows specifics mocked)
Windows-LTSC-Repair.spec    # PyInstaller release spec (onefile, windowed, uac_admin, icon)
packaging/
  app.manifest              # Standalone requireAdministrator + PerMonitorV2 manifest
  build_windows.bat         # One-command Windows build (tests gate the build)
```

### Engineering highlights ⚡

- **Race-free dispatch:** only one repair can run at a time (non-blocking
  lock); action buttons disable while running, GUI never freezes.
- **Thread-safe logging:** workers only append entries; the main thread
  renders them via a 250 ms poller — no cross-thread Tk calls.
- **Every command has a timeout** — a hung repair can never hang the app.
- **Verified service stops:** `sc stop` + state polling (handles shared
  svchost services) instead of fire-and-forget `net stop`.
- **Safe archive model:** `SoftwareDistribution` / `catroot2` are renamed
  to timestamped backups (never hard-deleted), and old backups are
  cleaned up automatically.
- **Registry-gated service configuration:** only services that actually
  exist on the running SKU are touched (CDPSvc, WlanSvc, NcdAutoSetup are
  absent on many LTSC images).
- **Retroactive translation:** switching AR/EN re-renders the whole log,
  with per-entry timestamps preserved.
- **Security hardening:** v1 added `NetworkService`/`LocalService` to the
  local **Administrators** group — a severe privilege-escalation
  misconfiguration that has been removed and is now blocked by a
  regression unit test.
- **Locale-independent service control:** service states are queried via
  the SCM API (`QueryServiceStatusEx`), not by parsing `sc query` text —
  `sc.exe` output is localized and would silently break the tool on
  non-English Windows.
- **Hard deadlines everywhere:** streamed commands (DISM/SFC/CHKDSK) run
  under a watchdog that kills stalled processes, so a hung repair can
  never freeze the worker or hold the UI busy-lock.
- **%SystemRoot% aware:** never assumes Windows lives on `C:\`.

## Running from source 📦

```bash
pip install -r requirements.txt
python FixTool.py        # UAC prompt appears automatically
```

## Building the executable 🚀

The release pipeline is spec-driven and **gated by the test suite** — run
this single command on a Windows host (PyInstaller does not
cross-compile, so the .exe must be produced on Windows):

```bat
packaging\build_windows.bat
```

which is equivalent to:

```bash
python -m pip install -r requirements.txt pyinstaller
python -m unittest discover -s tests        # build aborts on failure
python -m PyInstaller --noconfirm --clean Windows-LTSC-Repair.spec
```

Output: `dist\Windows-LTSC-Repair.exe` — a single onefile, windowed
executable with the multi-resolution icon and an embedded
`requireAdministrator` manifest (`uac_admin=True` in the spec; a
standalone manifest with PerMonitorV2 DPI awareness is also provided at
`packaging/app.manifest` for MSVC/embedding workflows). The spec
explicitly collects customtkinter's theme assets and pins the
`repair_core` package, so no dependency can be silently dropped.

> Note: the app also **self-elevates** (with correct argv quoting) when
> run from source — `python FixTool.py` — even without the manifest.

## Tests 🧪

The core is fully testable on any OS (Linux CI included) — all Windows
specifics are mocked:

```bash
python -m unittest discover -s tests -v
```

## Log file 📄

A live mirror of the on-screen event log is written to
`Desktop\Fixer_Events_Log.txt` (falls back to the user profile when the
Desktop is redirected, e.g. OneDrive).

## Notes ℹ️

- The **network repair** requires a reboot to fully apply (Winsock/IP
  resets) — the tool tells you when.
- **DISM** may use Windows Update as a repair source; on LTSC images
  without update connectivity, mount a matching ISO and use
  `/Source:<wim>` for faster repairs.
- **SFC** results that could not be repaired automatically are detailed
  in `C:\Windows\Logs\CBS\CBS.log`.
