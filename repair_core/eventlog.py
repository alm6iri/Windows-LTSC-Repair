# -*- coding: utf-8 -*-
"""Thread-safe event log store + desktop log-file writer.

Entries keep their own timestamp (v1 stamped the whole log with a single
"now" on every refresh) and their translation key + params, so switching
the UI language retroactively translates the entire history while raw
command/output lines stay untouched.

File writes happen exclusively on the GUI polling thread - worker
threads only append in-memory entries (list.append is atomic under the
GIL), which eliminates interleaved/partial writes.
"""

import os
import time


class EventLog(object):
    def __init__(self, path=None):
        self.entries = []
        self.path = path or default_log_path()

    def add(self, key=None, params=(), raw=None, level="info", ts=None):
        """Append an entry. ``key`` entries are translatable; ``raw``
        entries are verbatim text (commands, DISM/SFC output)."""
        self.entries.append({
            "ts": ts or time.strftime("%Y-%m-%d %H:%M:%S"),
            "key": key,
            "params": tuple(params or ()),
            "raw": raw,
            "level": level,
        })

    def render(self, strings, entries=None):
        """Render entries into display lines using a strings table.

        ``entries`` defaults to the live history; the GUI passes a
        snapshot so worker-thread appends can never race the render."""
        from .strings import render as _render  # local import: no cycle risk
        lines = []
        for entry in (self.entries if entries is None else entries):
            if entry["key"] is not None:
                text = _render(strings, entry["key"], entry["params"])
            else:
                text = entry["raw"]
            prefix = ""
            if entry["level"] == "warn":
                prefix = "[!] "
            elif entry["level"] == "cmd":
                prefix = "  > "
            lines.append("[{0}] {1}{2}".format(entry["ts"], prefix, text))
        return lines

    def save(self, strings):
        """Write the current history to the log file (snapshot semantics -
        the file always mirrors the live on-screen log). Never raises:
        logging must not kill a repair.

        The write goes to a sibling temp file and is atomically replaced
        over the real log, so a crash or power loss can never leave a
        half-written/truncated log behind."""
        temporary = self.path + ".tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                handle.write(
                    "===== FixTool session {0} =====\n\n".format(
                        time.strftime("%Y-%m-%d %H:%M:%S")
                    )
                )
                for line in self.render(strings, self.entries[:]):
                    handle.write(line + "\n")
            os.replace(temporary, self.path)
            return True
        except OSError:
            try:
                if os.path.exists(temporary):
                    os.remove(temporary)
            except OSError:
                pass
            return False


def default_log_path():
    """Desktop path with OneDrive-redirect tolerance: if the Desktop
    folder is missing/redirected we fall back to the user profile root."""
    profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    candidates = [
        os.path.join(profile, "Desktop"),
        profile,
    ]
    for folder in candidates:
        if os.path.isdir(folder):
            return os.path.join(folder, "Fixer_Events_Log.txt")
    return os.path.join(profile, "Fixer_Events_Log.txt")
