# -*- coding: utf-8 -*-
"""
MCP Server for Windows-LTSC-Repair.

Exposes the headless repair_core engine as callable MCP tools so that
AI agents (Claude, Cline, Cursor, ...) can programmatically repair a
Windows machine over the Model Context Protocol.

Design invariants:
* Imports ONLY repair_core - never FixTool.py or customtkinter. The GUI
  and the AI agent share the same engine but are strictly decoupled.
* Every tool returns a structured JSON payload (status / events / target)
  instead of human-oriented free text, so a model can branch on results.
* Only ONE repair runs at a time (a process-wide lock); concurrent calls
  are rejected with status "busy" rather than corrupting system state.
* Non-admin execution is detected and reported as status "blocked",
  never silently attempted.
"""

import json
import threading
import time
from typing import Any, Dict, List, Optional

from repair_core import __version__ as CORE_VERSION
from repair_core import disk_repair, network_repair, platform_info
from repair_core import strings as strings_mod
from repair_core import system_repair, time_repair, update_repair
from repair_core.eventlog import EventLog
from repair_core.runner import Runner

try:  # The MCP SDK is a runtime dependency, not required for schema dumping.
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - exercised only in --dump-schemas
    FastMCP = None

EN_STRINGS = strings_mod.STRINGS["EN"]

# ---------------------------------------------------------------------------
# Tool registry - single source of truth for MCP tools, CLI schemas and docs.
# (repairs is a list; strings.STRINGS is a dict -> use list for order.)
# ---------------------------------------------------------------------------

REPAIR_MODULES = [
    ("network_repair", network_repair, "net_start", "net_end"),
    ("update_repair", update_repair, "upd_start", "upd_end"),
    ("time_repair", time_repair, "time_start", "time_end"),
    ("system_repair", system_repair, "sys_start", "sys_end"),
    ("disk_repair", disk_repair, "disk_start", "disk_end"),
]

TOOL_DESCRIPTIONS = {
    "detect_platform": (
        "Read-only system inspection. Returns Windows edition/build, "
        "elevation (UAC) status and architecture. Run this first."
    ),
    "run_network_repair": (
        "Deep network stack repair: resets Winsock/TCP-IP, rebuilds the "
        "network core services and refreshes adapters. Full effect needs "
        "a reboot. Considered medium-risk (drops connectivity briefly)."
    ),
    "run_update_repair": (
        "Windows Update maintenance: archives corrupted "
        "SoftwareDistribution/catroot2 stores, rebuilds update services, "
        "rescans for updates. Considered medium-risk."
    ),
    "run_time_repair": (
        "Re-registers the Windows Time service, resyncs against the "
        "configured NTP server and fixes clock skew. Low-risk."
    ),
    "run_system_repair": (
        "Deep system file repair: SFC scan followed by DISM "
        "RestoreHealth. Long-running (can exceed 15 minutes). Low-risk "
        "but CPU intensive."
    ),
    "run_disk_repair": (
        "Filesystem health check via CHKDSK. Schedules a scan that may "
        "require a reboot if the volume is locked. Low-risk."
    ),
    "reboot_system": (
        "Reboot the machine to apply pending repairs (network stack, "
        "CHKDSK scan). Ask the user for confirmation before calling."
    ),
}

# Dangerous tools require explicit user confirmation by the calling agent.
DESTRUCTIVE_TOOLS = {"reboot_system"}

_LOCK = threading.Lock()

mcp = FastMCP("windows-ltsc-repair") if FastMCP else None  # pragma: no cover


# ---------------------------------------------------------------------------
# Structured response helpers
# ---------------------------------------------------------------------------

def _translate(key: Optional[str], params: tuple) -> Optional[str]:
    """Render a translatable event key in English (the AI lingua franca).
    Returns None for raw-only entries."""
    if not key:
        return None
    try:
        return EN_STRINGS[key].format(*params)
    except Exception:
        return None


def _event_to_json(entry: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "ts": entry.get("ts"),
        "level": entry.get("level", "info"),
        "message": _translate(entry.get("key"), entry.get("params", ())),
    }
    raw = entry.get("raw")
    if raw is not None:
        out["raw"] = raw
    if out["message"] is None and raw is None:
        out["message"] = "(untranslated event: %s)" % entry.get("key")
    return out


def _on_event(eventlog: EventLog) -> None:
    """Runner callback - appends events into the shared log store."""
    def handler(key=None, params=(), raw=None, level="info", ts=None):
        eventlog.add(key=key, params=params, raw=raw, level=level, ts=ts)
    return handler


def _build_response(tool: str, eventlog: EventLog, started: float,
                    status: str, extra: Optional[Dict] = None) -> Dict[str, Any]:
    payload = {
        "tool": tool,
        "status": status,
        "engine_version": CORE_VERSION,
        "duration_seconds": round(time.time() - started, 1),
        "events": [_event_to_json(e) for e in eventlog.entries],
        "target_system": None,
    }
    if extra:
        payload.update(extra)
    return payload


def _run_repair_tool(tool: str, module, start_key: str, end_key: str) -> Dict[str, Any]:
    """Shared executor for all repair tools."""
    if not _LOCK.acquire(blocking=False):
        return {
            "tool": tool,
            "status": "busy",
            "engine_version": CORE_VERSION,
            "error": "Another repair is already running in this server "
                     "instance. Wait for it to finish before starting a new one.",
        }

    started = time.time()
    eventlog = EventLog()
    try:
        info = platform_info.detect()
        if not info.get("is_windows"):
            return _build_response(tool, eventlog, started, "blocked", {
                "error": "This tool only works on Windows hosts.",
            })
        if not info.get("is_admin"):
            return _build_response(tool, eventlog, started, "blocked", {
                "error": "Administrator privileges are required. Relaunch "
                         "the MCP server elevated (UAC) and retry.",
                "target_system": info.get("label"),
            })

        runner = Runner(_on_event(eventlog))
        runner.log(start_key, level="info")
        module.repair(runner, info)
        runner.log(end_key, level="info")
        return _build_response(tool, eventlog, started, "success", {
            "target_system": info.get("label"),
            "reboot_recommended": tool in {"run_network_repair", "run_disk_repair",
                                           "run_update_repair"},
        })
    except Exception as exc:  # noqa: BLE001 - structured failure for the agent
        return _build_response(tool, eventlog, started, "failed", {
            "error": "%s: %s" % (type(exc).__name__, exc),
        })
    finally:
        _LOCK.release()


def _detect_platform() -> Dict[str, Any]:
    started = time.time()
    eventlog = EventLog()
    try:
        info = platform_info.detect()
        runner = Runner(_on_event(eventlog))
        runner.log("sys_lbl", params=(info.get("label", "?"),), level="info")
        return _build_response("detect_platform", eventlog, started, "success", {
            "target_system": info.get("label"),
            "details": info,
        })
    except Exception as exc:  # noqa: BLE001
        return _build_response("detect_platform", eventlog, started, "failed", {
            "error": "%s: %s" % (type(exc).__name__, exc),
        })


def _reboot_system(confirm: bool) -> Dict[str, Any]:
    """Elevated reboot - gated behind an explicit boolean confirmation."""
    started = time.time()
    eventlog = EventLog()
    if not confirm:
        return _build_response("reboot_system", eventlog, started, "rejected", {
            "error": "confirm must be true. Ask the user first.",
        })
    try:
        info = platform_info.detect()
        if not info.get("is_admin"):
            return _build_response("reboot_system", eventlog, started, "blocked", {
                "error": "Administrator privileges are required.",
            })
        import subprocess
        subprocess.run(["shutdown", "/r", "/t", "5"], check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        return _build_response("reboot_system", eventlog, started, "success", {
            "target_system": info.get("label"),
            "note": "Reboot scheduled in 5 seconds (shutdown /r /t 5).",
        })
    except Exception as exc:  # noqa: BLE001
        return _build_response("reboot_system", eventlog, started, "failed", {
            "error": "%s: %s" % (type(exc).__name__, exc),
        })


# ---------------------------------------------------------------------------
# MCP tool registration (guarded so --dump-schemas works without the SDK)
# ---------------------------------------------------------------------------

if mcp is not None:  # pragma: no cover - runtime path only

    @mcp.tool()
    def detect_platform() -> Dict[str, Any]:
        """Read-only Windows detection: edition, build, elevation, arch."""
        return _detect_platform()

    @mcp.tool()
    def run_network_repair() -> Dict[str, Any]:
        """Deep network stack repair (Winsock/TCP-IP reset, service rebuild)."""
        return _run_repair_tool("run_network_repair", network_repair,
                                "net_start", "net_end")

    @mcp.tool()
    def run_update_repair() -> Dict[str, Any]:
        """Windows Update maintenance (archive stores, rebuild services)."""
        return _run_repair_tool("run_update_repair", update_repair,
                                "upd_start", "upd_end")

    @mcp.tool()
    def run_time_repair() -> Dict[str, Any]:
        """Windows Time service re-registration and NTP resync."""
        return _run_repair_tool("run_time_repair", time_repair,
                                "time_start", "time_end")

    @mcp.tool()
    def run_system_repair() -> Dict[str, Any]:
        """SFC + DISM deep system-file repair. Long-running."""
        return _run_repair_tool("run_system_repair", system_repair,
                                "sys_start", "sys_end")

    @mcp.tool()
    def run_disk_repair() -> Dict[str, Any]:
        """CHKDSK filesystem health check; may schedule a reboot scan."""
        return _run_repair_tool("run_disk_repair", disk_repair,
                                "disk_start", "disk_end")

    @mcp.tool()
    def reboot_system(confirm: bool) -> Dict[str, Any]:
        """Reboot the machine to apply pending repairs. Requires confirm=true."""
        return _reboot_system(confirm)


# ---------------------------------------------------------------------------
# CLI: dump function-calling schemas for OpenAI/Anthropic style agents
# ---------------------------------------------------------------------------

def dump_schemas(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generate OpenAPI/Function-Calling JSON Schemas for every tool."""
    props = {}
    required = []
    for name, desc in TOOL_DESCRIPTIONS.items():
        schema: Dict[str, Any] = {"type": "object", "properties": {}}
        if name == "reboot_system":
            schema["properties"]["confirm"] = {
                "type": "boolean",
                "description": "Must be true to actually reboot.",
            }
            required.append("confirm")
        props[name] = {
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": schema,
            },
        }
        if required:
            schema["required"] = required
    schemas = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "server": "windows-ltsc-repair",
        "engine_version": CORE_VERSION,
        "tools": props,
    }
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(schemas, fh, indent=2, ensure_ascii=False)
    return [props[name] for name in TOOL_DESCRIPTIONS]


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Windows-LTSC-Repair MCP server")
    parser.add_argument("--dump-schemas", metavar="PATH",
                        help="Write function-calling JSON schemas to PATH and exit")
    args = parser.parse_args()
    if args.dump_schemas:
        dump_schemas(args.dump_schemas)
        return
    if mcp is None:
        raise SystemExit("The 'mcp' package is required: pip install mcp")
    mcp.run()  # pragma: no cover


if __name__ == "__main__":
    main()
