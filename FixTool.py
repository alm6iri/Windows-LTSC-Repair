# -*- coding: utf-8 -*-
"""
Project:  Windows Repair Tool (LTSC + all Windows 10/11 editions)
GUI:      CustomTkinter front-end. All repair logic lives in repair_core.

Boot sequence:
  1. Platform guard (Windows only, graceful message otherwise).
  2. UAC elevation with correct argv quoting (v1 lost quoting and died
     silently when the user declined the prompt).
  3. DPI awareness for crisp rendering on scaled displays.
  4. GUI with race-free operation dispatch: one operation at a time,
     buttons disabled while running, live streaming log.
"""

import os
import sys
import ctypes
import subprocess
import threading
import time

# ---------------------------------------------------------------------------
# Core engine (platform-independent and unit-testable without Windows)
# ---------------------------------------------------------------------------
from repair_core import platform_info
from repair_core import network_repair
from repair_core import update_repair
from repair_core import time_repair
from repair_core import system_repair
from repair_core import disk_repair
from repair_core import strings as strings_mod
from repair_core import __version__ as CORE_VERSION
from repair_core.eventlog import EventLog
from repair_core.runner import Runner


# ---------------------------------------------------------------------------
# Boot helpers (no customtkinter dependency - usable pre-GUI)
# ---------------------------------------------------------------------------

def _is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _message_box(text, caption, kind="error"):
    """Native Win32 message box - works before/without any GUI toolkit."""
    try:
        icon = 0x40 if kind == "info" else 0x10
        ctypes.windll.user32.MessageBoxW(0, text, caption, icon)
    except Exception:
        pass


def _relaunch_elevated():
    """Relaunch the current process elevated (UAC). Returns a value
    greater than 32 on success (ShellExecuteW convention), 0 on failure."""
    if getattr(sys, "frozen", False):
        # PyInstaller exe: the executable IS the program.
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        # Dev mode: python.exe "<script.py>" <args...> - properly quoted.
        params = subprocess.list2cmdline(sys.argv)
    try:
        shell32 = ctypes.windll.shell32
        # Explicit prototypes: ShellExecuteW returns HINSTANCE, which is
        # POINTER-SIZED - with ctypes' default 32-bit c_int restype the
        # value can be truncated on 64-bit Windows.
        shell32.ShellExecuteW.restype = ctypes.c_void_p
        shell32.ShellExecuteW.argtypes = [
            ctypes.c_void_p,        # hwnd
            ctypes.c_wchar_p,       # lpVerb
            ctypes.c_wchar_p,       # lpFile
            ctypes.c_wchar_p,       # lpParameters
            ctypes.c_wchar_p,       # lpDirectory
            ctypes.c_int,           # nShowCmd
        ]
        ret = shell32.ShellExecuteW(
            None, "runas", sys.executable, params or None, None, 1)
        return 0 if ret is None else int(ret)
    except Exception:
        return 0


def _enable_dpi_awareness():
    """Crisp text on high-DPI displays.

    Deliberately SYSTEM-DPI-aware (SetProcessDPIAware) and NOT
    Per-Monitor-V2: Tk 8.6 does not handle WM_DPICHANGED, so PMv2 would
    leave the window unscaled after a monitor change (blurry/wrong
    sizing). System-aware + CustomTkinter's internal scaling detection
    gives the sharpest RELIABLE rendering on every supported build.
    Do not "upgrade" this to PMv2 without changing the GUI toolkit."""
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _try_load_gui():
    try:
        import customtkinter as ctk
        return ctk
    except ImportError:
        ar = strings_mod.STRINGS["AR"]
        _message_box(ar["err_ctk_msg"], ar["err_ctk_title"])
        return None


# ---------------------------------------------------------------------------
# The application
# ---------------------------------------------------------------------------

class WindowsRepairApp(object):
    """Composition root: wires the GUI to the repair_core engine."""

    # operation id -> (module, start-key, end-key)
    OPERATIONS = {
        "net": (network_repair, "net_start", "net_end"),
        "upd": (update_repair, "upd_start", "upd_end"),
        "time": (time_repair, "time_start", "time_end"),
        "sys": (system_repair, "sys_start", "sys_end"),
        "disk": (disk_repair, "disk_start", "disk_end"),
    }

    def __init__(self, ctk):
        self.ctk = ctk
        self.lang = "AR"
        self.info = platform_info.detect()
        self.log = EventLog()
        self.runner = Runner(on_event=self._on_core_event)
        self._busy_lock = threading.Lock()
        self._rendered_count = -1

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self._apply_window_icon()
        self._build_ui()
        self.log.add("start_msg")
        self.log.add(raw=self.info.summary())
        self._refresh(force=True)
        self.root.after(250, self._poll_log)

    # ------------------------------------------------------------------ core
    @property
    def s(self):
        return strings_mod.STRINGS[self.lang]

    def _window_title(self):
        """Window title carries the release version (single source of
        truth: repair_core.__version__)."""
        return "{0} v{1}".format(self.s["title_win"], CORE_VERSION)

    def _on_core_event(self, key, params, raw, level):
        """Runner callback - executes on worker threads. Only appends to
        the in-memory log; every GUI/file touch happens on the main
        thread inside _poll_log (thread-safe by construction)."""
        self.log.add(key=key, params=params, raw=raw, level=level)

    # -------------------------------------------------------------------- ui
    def _apply_window_icon(self):
        """Icon lookup order: PyInstaller bundle (sys._MEIPASS, populated
        by the spec's datas) -> script directory -> skip silently."""
        candidates = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, "app_icon.ico"))
        candidates.append(os.path.join(
            os.path.dirname(os.path.abspath(sys.argv[0])), "app_icon.ico"))
        for icon in candidates:
            if os.path.isfile(icon):
                try:
                    self.root.iconbitmap(icon)
                except Exception:
                    pass
                return

    def _build_ui(self):
        s = self.s
        self.root.title(self._window_title())
        self.root.geometry("880x580")
        self.root.resizable(False, False)

        self.title_label = self.ctk.CTkLabel(
            self.root, text=s["header"],
            font=self.ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color="#61AFEF")
        self.title_label.pack(pady=(15, 2))

        self.subtitle_label = self.ctk.CTkLabel(
            self.root, text=s["subheader"],
            font=self.ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
            text_color="#ABB2BF")
        self.subtitle_label.pack(pady=(0, 4))

        self.sysinfo_label = self.ctk.CTkLabel(
            self.root, text=s["sys_lbl"].format(self.info.summary()),
            font=self.ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#98C379")
        self.sysinfo_label.pack(pady=(0, 12))

        # ---- action buttons column ----
        self.button_frame = self.ctk.CTkFrame(self.root, width=230,
                                              corner_radius=10)
        self.button_frame.pack_propagate(False)

        def make_button(text, color, hover, text_color, cmd):
            return self.ctk.CTkButton(
                self.button_frame, text=text, fg_color=color,
                hover_color=hover, text_color=text_color,
                font=self.ctk.CTkFont(family="Segoe UI", size=12,
                                      weight="bold"),
                height=32, command=cmd)

        self.btn_net = make_button(
            s["btn_net"], "#98C379", "#7CB342", "#1E1E1E",
            lambda: self._run_operation("net"))
        self.btn_upd = make_button(
            s["btn_upd"], "#E5C07B", "#D1A139", "#1E1E1E",
            lambda: self._run_operation("upd"))
        self.btn_time = make_button(
            s["btn_time"], "#61AFEF", "#4B96DB", "#1E1E1E",
            lambda: self._run_operation("time"))
        self.btn_sys = make_button(
            s["btn_sys"], "#C678DD", "#A85BD3", "#1E1E1E",
            lambda: self._run_operation("sys"))
        self.btn_disk = make_button(
            s["btn_disk"], "#56B6C2", "#3E999F", "#1E1E1E",
            lambda: self._run_operation("disk"))
        self.btn_reboot = make_button(
            s["btn_reboot"], "#E06C75", "#D32F2F", "#FFFFFF",
            self.show_reboot_window)
        self.btn_lang = make_button(
            s["lang_btn"], "#4B5263", "#5C6370", "#FFFFFF",
            self.toggle_language)

        for btn in (self.btn_net, self.btn_upd, self.btn_time,
                    self.btn_sys, self.btn_disk):
            btn.pack(pady=(10, 0), padx=15, fill="x")
        self.btn_lang.pack(pady=(10, 0), padx=15, fill="x")
        self.btn_reboot.pack(pady=(25, 10), padx=15, fill="x")

        self._action_buttons = [self.btn_net, self.btn_upd, self.btn_time,
                                self.btn_sys, self.btn_disk]

        # ---- log panel ----
        self.log_frame = self.ctk.CTkFrame(self.root, corner_radius=10)
        self.log_label = self.ctk.CTkLabel(
            self.log_frame, text=s["log_lbl"],
            font=self.ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
        self.log_label.pack(anchor=s["anchor"], padx=15, pady=5)

        self.log_text = self.ctk.CTkTextbox(
            self.log_frame,
            font=self.ctk.CTkFont(family="Consolas", size=11),
            fg_color="#1E1E1E", text_color="#ABB2BF", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        self.log_text.configure(state="disabled")

        # ---- status bar ----
        self.status_label = self.ctk.CTkLabel(
            self.root, text=s["status_ready"],
            font=self.ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#98C379", anchor=s["anchor"])
        self.status_label.pack(fill="x", padx=20, pady=(0, 8))

        self._apply_layout_direction()


    # ------------------------------------------------------- layout / i18n
    def _apply_layout_direction(self):
        """Mirror the whole layout (RTL for Arabic, LTR for English)."""
        s = self.s
        self.button_frame.pack_forget()
        self.log_frame.pack_forget()
        self.button_frame.pack(side=s["side_btn"], fill="y",
                               padx=20, pady=(0, 10))
        self.log_frame.pack(side=s["side_log"], fill="both", expand=True,
                            padx=20, pady=(0, 10))
        self.log_text.configure(state="normal")
        self.log_text.tag_config("align", justify=s["justify"])
        self.log_text.configure(state="disabled")

    def toggle_language(self):
        """Instant AR/EN switch, including retroactive log translation."""
        self.lang = "EN" if self.lang == "AR" else "AR"
        s = self.s
        self.root.title(self._window_title())
        self.title_label.configure(text=s["header"])
        self.subtitle_label.configure(text=s["subheader"])
        self.sysinfo_label.configure(
            text=s["sys_lbl"].format(self.info.summary()))
        self.btn_net.configure(text=s["btn_net"])
        self.btn_upd.configure(text=s["btn_upd"])
        self.btn_time.configure(text=s["btn_time"])
        self.btn_sys.configure(text=s["btn_sys"])
        self.btn_disk.configure(text=s["btn_disk"])
        self.btn_reboot.configure(text=s["btn_reboot"])
        self.btn_lang.configure(text=s["lang_btn"])
        # Preserve the busy state across the language switch (the text
        # must translate without resetting the visual state).
        busy = self._busy_lock.locked()
        self.status_label.configure(
            text=s["status_busy"] if busy else s["status_ready"],
            text_color="#E5C07B" if busy else "#98C379",
            anchor=s["anchor"])
        self.log_label.configure(text=s["log_lbl"])
        self._apply_layout_direction()
        self._refresh(force=True)

    # ------------------------------------------------------------- log loop
    def _poll_log(self):
        """Main-thread pump (the ONLY place that touches Tk widgets):
        repaints the log when workers appended entries, applies pending
        busy-state transitions, and mirrors the log to disk. An exception
        in one cycle must never kill the pump."""
        try:
            if getattr(self, "_pending_busy_off", False):
                self._pending_busy_off = False
                self._set_busy(False)
            self._refresh()
        except Exception:
            pass
        finally:
            self.root.after(250, self._poll_log)

    def _refresh(self, force=False):
        if not force and len(self.log.entries) == self._rendered_count:
            return
        self._rendered_count = len(self.log.entries)
        lines = self.log.render(self.s)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        for line in lines:
            self.log_text.insert("end", line + "\n", "align")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        # Throttled disk mirror (max once per 2s) so DISM's streamed
        # output cannot cause a write storm.
        now = time.monotonic()
        if force or now - getattr(self, "_last_save", 0.0) >= 2.0:
            self._last_save = now
            self.log.save(self.s)  # best-effort, never raises


    # ------------------------------------------------------------ operations
    def _set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for btn in self._action_buttons:
            btn.configure(state=state)
        # The reboot button is ALSO gated: rebooting mid-repair (e.g.
        # while an archive rename is in flight) must not be possible.
        self.btn_reboot.configure(state=state)
        self.status_label.configure(
            text=self.s["status_busy"] if busy else self.s["status_ready"],
            text_color="#E5C07B" if busy else "#98C379")

    def _run_operation(self, op_id):
        """Race-free dispatch: a non-blocking lock guarantees only one
        repair runs at a time; the GUI stays responsive via the poller."""
        module, start_key, end_key = self.OPERATIONS[op_id]
        if not self._busy_lock.acquire(blocking=False):
            return
        self._set_busy(True)
        self.log.add(start_key)

        def work():
            result = {}
            try:
                result = module.repair(self.runner, self.info) or {}
            except Exception as exc:  # never let a worker kill the app
                self.log.add("err_generic", (str(exc),), level="warn")
            finally:
                self.log.add(end_key)
                if result.get("reboot_required"):
                    self.log.add("reboot_required_note")
                self._busy_lock.release()
                # Never call Tk from a worker thread: the main-thread
                # poller consumes this flag within 250 ms.
                self._pending_busy_off = True

        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------------- reboot
    def show_reboot_window(self):
        if self._busy_lock.locked():
            return  # an operation is in flight; rebooting now is unsafe
        s = self.s
        win = self.ctk.CTkToplevel(self.root)
        win.title(s["reboot_title"])
        win.geometry("420x190")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.grab_set()

        lbl = self.ctk.CTkLabel(
            win, text=s["reboot_msg"],
            font=self.ctk.CTkFont(family="Segoe UI", size=13, weight="bold"))
        lbl.pack(pady=20)

        frame = self.ctk.CTkFrame(win, fg_color="transparent")
        frame.pack(pady=10)

        def do_reboot():
            try:
                subprocess.run(["shutdown", "/r", "/t", "0", "/f"],
                               timeout=15,
                               creationflags=getattr(
                                   subprocess, "CREATE_NO_WINDOW", 0))
            except Exception:
                pass

        self.ctk.CTkButton(
            frame, text=s["reboot_yes"], fg_color="#E06C75",
            hover_color="#D32F2F", width=140,
            command=do_reboot).grid(row=0, column=0, padx=10)
        self.ctk.CTkButton(
            frame, text=s["reboot_no"], fg_color="#4B5263",
            hover_color="#5C6370", width=140,
            command=win.destroy).grid(row=0, column=1, padx=10)

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # 1. Platform guard (dev/CI sandbox friendly) - localized message.
    if os.name != "nt":
        ar = strings_mod.STRINGS["AR"]
        sys.stderr.write(ar["err_unsupported_msg"] + "\n")
        return 1

    # 2. UAC elevation (correct quoting + graceful decline handling).
    if not _is_admin():
        ret = _relaunch_elevated()
        if ret <= 32:
            _message_box(strings_mod.STRINGS["AR"]["err_admin_msg"],
                         strings_mod.STRINGS["AR"]["err_admin_title"])
            return 1
        return 0  # elevated copy is starting; this instance steps aside.

    # 3. DPI awareness before any widget is created.
    _enable_dpi_awareness()

    # 4. GUI.
    ctk = _try_load_gui()
    if ctk is None:
        return 1
    try:
        app = WindowsRepairApp(ctk)
        app.run()
    except Exception as exc:
        _message_box(strings_mod.STRINGS["AR"]["err_generic"].format(exc),
                     "Windows Repair Tool")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

