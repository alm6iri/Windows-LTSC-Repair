# -*- coding: utf-8 -*-
"""Safe, console-free command runner and Windows service manager.

Design goals:
* No black console flashes (CREATE_NO_WINDOW) - mandatory for a GUI tool.
* Every command has a timeout - a hung repair must never hang the app.
* Structured events instead of blind execution: the GUI log receives
  what ran, what failed and why, in both Arabic and English.
* Service operations (stop/start/config) are poll-based with retries so
  shared svchost services (wuauserv etc.) are handled reliably on every
  build from 1507 to 24H2.
* No ``shell=True`` and no string interpolation of user data anywhere:
  commands are passed as argv lists, eliminating quoting/injection bugs.
"""

import glob
import os
import re
import shutil
import stat
import subprocess
import time

# 0x08000000 = CREATE_NO_WINDOW (Windows-only constant)
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_STATE_RE = re.compile(r"STATE\s*:\s*\d+\s+([A-Z]+)")


class CmdResult(object):
    """Uniform result object; ``rc`` is None when the command could not be
    launched at all (missing binary / timeout)."""

    __slots__ = ("rc", "out", "err")

    def __init__(self, rc=None, out="", err=""):
        self.rc = rc
        self.out = out or ""
        self.err = err or ""

    @property
    def ok(self):
        return self.rc == 0


def fmt_cmd(cmd):
    """Human-readable one-line rendering of an argv list (or raw string)."""
    if isinstance(cmd, str):
        return cmd
    return subprocess.list2cmdline(cmd)


class Runner(object):
    """Executes repair commands and reports every step through ``on_event``.

    ``on_event(key, params, raw, level)`` is called from worker threads.
    """

    def __init__(self, on_event):
        self.on_event = on_event

    # ------------------------------------------------------------------ events
    def note(self, key, params=(), level="info"):
        self.on_event(key, tuple(params), None, level)

    def _raw(self, text, level="info"):
        self.on_event(None, (), text, level)

    def raw(self, text, level="info"):
        """Report a raw (non-translatable) line, e.g. command output."""
        self._raw(text, level)

    # ------------------------------------------------------------- subprocess
    def run(self, cmd, timeout=120, report=True, input=None):
        """Run a command, capture output, never raise. Returns CmdResult.
        ``input`` pipes stdin (used to answer CHKDSK's Y/N reboot prompt)."""
        if report:
            self._raw(fmt_cmd(cmd), "cmd")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                input=input,
                creationflags=_NO_WINDOW,
            )
            result = CmdResult(proc.returncode, proc.stdout, proc.stderr)
        except subprocess.TimeoutExpired:
            self.note("cmd_timeout", (fmt_cmd(cmd), timeout), "warn")
            return CmdResult(None)
        except (OSError, ValueError) as exc:
            # FileNotFoundError (binary removed, e.g. wmic on 24H2) and
            # anything else - always degrade, never crash the worker.
            self.note("cmd_missing", (fmt_cmd(cmd), str(exc)), "warn")
            return CmdResult(None)
        if not result.ok and report:
            self.note("cmd_failed", (result.rc, fmt_cmd(cmd)), "warn")
        return result

    def run_stream(self, cmd, timeout=3600, on_line=None):
        """Run a long command (DISM/SFC) and stream stdout lines live.
        Returns the exit code (None on launch/timeout failure)."""
        self._raw(fmt_cmd(cmd), "cmd")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=_NO_WINDOW,
            )
        except (OSError, ValueError) as exc:
            self.note("cmd_missing", (fmt_cmd(cmd), str(exc)), "warn")
            return None
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if line and on_line:
                    on_line(line)
            proc.wait(timeout=max(1, timeout))
        except subprocess.TimeoutExpired:
            proc.kill()
            self.note("cmd_timeout", (fmt_cmd(cmd), timeout), "warn")
            return None
        except OSError as exc:
            self.note("cmd_failed", (None, str(exc)), "warn")
            return None
        return proc.returncode

    def run_bytes(self, cmd, timeout=3600):
        """Run and capture raw bytes (needed for SFC, whose redirected
        output is UTF-16LE on all supported builds)."""
        self._raw(fmt_cmd(cmd), "cmd")
        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=timeout,
                creationflags=_NO_WINDOW,
            )
        except subprocess.TimeoutExpired:
            self.note("cmd_timeout", (fmt_cmd(cmd), timeout), "warn")
            return None, b""
        except (OSError, ValueError) as exc:
            self.note("cmd_missing", (fmt_cmd(cmd), str(exc)), "warn")
            return None, b""
        return proc.returncode, proc.stdout

    # --------------------------------------------------------------- services
    def service_state(self, name):
        """Current service state string (RUNNING/STOPPED/...) or None when
        the service cannot be queried."""
        res = self.run(["sc", "query", name], timeout=30, report=False)
        if not res.ok:
            return None
        match = _STATE_RE.search(res.out + res.err)
        return match.group(1) if match else None

    def stop_service(self, name, timeout=30):
        """Stop a service and *wait* until it is really STOPPED.
        Returns True when stopped (or already stopped)."""
        state = self.service_state(name)
        if state in ("STOPPED",):
            return True
        if state is None:
            # Not installed or not queryable - nothing to do.
            return True
        self.run(["sc", "stop", name], timeout=30)
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(1.0)
            state = self.service_state(name)
            if state in ("STOPPED",):
                return True
            # STOP_PENDING keeps waiting; anything else (e.g. the service
            # disappeared) bails out safely.
            if state is None:
                return False
        self.note("service_stop_timeout", (name,), "warn")
        return False

    def start_service(self, name, wait=15, retries=1):
        """Start a service, retrying transient failures once.
        Non-fatal by design: failure is reported as a warning."""
        for attempt in range(retries + 1):
            state = self.service_state(name)
            if state == "RUNNING":
                return True
            self.run(["sc", "start", name], timeout=30)
            deadline = time.time() + wait
            while time.time() < deadline:
                time.sleep(1.0)
                if self.service_state(name) == "RUNNING":
                    return True
            if attempt < retries:
                time.sleep(2.0)
        # Demand-start services with nothing to do report non-zero exit
        # codes - treat as warning, not error, exactly like the OS does.
        self.note("service_start_failed", (name,), "warn")
        return False

    def set_start_mode(self, name, mode):
        """Configure a service start mode via `sc config name start= mode`
        (note: sc requires the token `start=` followed by the value)."""
        return self.run(
            ["sc", "config", name, "start=", mode], timeout=30
        ).ok

    # ------------------------------------------------------------ filesystem
    def rename_dir(self, path, suffix=".bak"):
        """Atomically archive a directory to `<path>.bak_<timestamp>`.
        Renaming (instead of deleting) lets Windows rebuild the folder
        while the old content stays recoverable - far safer than rd /s /q.
        Returns the new path, or None on failure (e.g. file locks)."""
        if not os.path.isdir(path):
            return None
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target = "{0}{1}_{2}".format(path, suffix, stamp)
        for _attempt in range(3):
            try:
                os.rename(path, target)
                return target
            except OSError:
                time.sleep(1.0)
        return None

    def delete_path(self, path):
        """Recursively delete a path, clearing read-only attributes first.
        Returns True on success."""
        if not os.path.exists(path):
            return True

        def _onerror(func, p, _exc):
            try:
                os.chmod(p, stat.S_IWRITE)
                func(p)
            except OSError:
                pass

        try:
            if os.path.isdir(path):
                shutil.rmtree(path, onerror=_onerror)
            else:
                os.chmod(path, stat.S_IWRITE)
                os.remove(path)
            return not os.path.exists(path)
        except OSError:
            return False

    def cleanup_backups(self, path, suffix=".bak"):
        """Remove leftovers from previous repair sessions:
        `<path>.bak_*` older archives - keeps the system tidy forever."""
        removed = 0
        for old in glob.glob(glob.escape(path) + suffix + "_*"):
            if self.delete_path(old):
                removed += 1
        return removed


def _selfcheck():
    """Import-time sanity: nothing to do yet; placeholder keeps the module
    importable even when trimmed by packers."""
    return True

